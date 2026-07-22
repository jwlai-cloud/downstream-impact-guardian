"""Downstream Impact Guardian — core loop entry point.

    python agent/main.py --pr-number 7 [--mode auto|live|offline] ...

Steps (CLAUDE.md): detect (dbt manifests + glossary) -> blast radius
(DataHub lineage + queries) -> writeback 1 (Data Contract) -> generate
compatibility code -> writeback 2 (PR comment).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import blast_radius, codegen, contract, dbt_state, pr_comment
from agent.config import Config
from agent.datahub_client import make_reader


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Downstream Impact Guardian")
    p.add_argument("--pr-number", type=int, required=True)
    p.add_argument("--prod-manifest",
                   default="dbt_demo_project/prod_state/manifest.json")
    p.add_argument("--pr-manifest",
                   default="dbt_demo_project/target/manifest.json")
    p.add_argument("--glossary",
                   default="dbt_demo_project/datahub/business_glossary.yml")
    p.add_argument("--mode", choices=["auto", "live", "offline"],
                   default="auto")
    p.add_argument("--output-dir", default=".dig_output",
                   help="Where generated artifacts get written")
    p.add_argument("--no-post", action="store_true",
                   help="Render but do not post the PR comment")
    p.add_argument("--strict", action="store_true",
                   help="Exit non-zero on HIGH/CRITICAL severity")
    return p.parse_args(argv)


def run(args) -> int:
    config = Config.from_env(mode=args.mode)
    reader = make_reader(config)
    print(f"[guardian] mode={config.mode}")

    # 1+2. Detect schema/logic changes (dbt state) and semantic drift.
    prod = dbt_state.load_manifest(args.prod_manifest)
    pr = dbt_state.load_manifest(args.pr_manifest)
    model_changes = dbt_state.diff_manifests(prod, pr)
    glossary_changes = dbt_state.diff_glossary(args.glossary, reader)
    if not model_changes and not glossary_changes:
        print("[guardian] no impactful changes detected — done")
        return 0
    suspected = dbt_state.find_suspected_drifts(pr, model_changes,
                                                glossary_changes, reader)
    print(f"[guardian] {len(model_changes)} model change(s), "
          f"{len(glossary_changes)} glossary drift(s), "
          f"{len(suspected)} suspected drift(s)")

    # 3. Blast radius from DataHub (live tables only — never PR state).
    consumers = {c.model_name: reader.get_downstream(c.model_name)
                 for c in model_changes}
    queries = {c.model_name: reader.get_queries(c.model_name)
               for c in model_changes}
    report = blast_radius.assess(model_changes, glossary_changes,
                                 consumers, queries, suspected)
    print(f"[guardian] severity={report.severity} score={report.score}")

    # Optional: ADK/Gemini narrative on top of the deterministic one.
    import os as _os
    if config.mode == "live" and (config.google_api_key
                                  or _os.environ.get("OPENAI_API_KEY")):
        from agent.adk_agent import enrich_narrative
        enrich_narrative(report, reader, config.google_api_key)
        print(f"[guardian] narrative source: {report.narrative_source}")

    # 4. Writeback 1 — one Data Contract per impacted model: breaking, or
    # drifted with known consumers (grill decision 2026-07-15, ADR-0009).
    pr_url = (f"https://github.com/{config.github_repository}/pull/"
              f"{args.pr_number}" if config.github_repository else
              f"PR #{args.pr_number}")
    targets = [c for c in model_changes
               if c.breaking or consumers.get(c.model_name)]
    contracts: list = []
    for target in targets:
        entity_urn = (reader.get_dataset_urn(target.model_name)
                      or config.dataset_urn(target.model_name))
        assertions = reader.get_assertions(target.model_name)
        result = contract.write_contract(
            reader if config.mode == "live" else None,
            entity_urn, assertions, pr_url,
            offline=config.mode != "live")
        result.model_name = target.model_name
        contracts.append(result)
        print(f"[guardian] contract[{target.model_name}]: {result.mode} "
              f"{result.urn or ''}")

    # 5. Generate mergeable compatibility code. The compat view must
    # reproduce what is LIVE, and DataHub — not the manifest's (possibly
    # partial) column docs — is the authority on that. Manifest columns
    # stay as fallback.
    for ch in model_changes:
        live_cols = [c["name"] for c in reader.get_schema(ch.model_name)]
        if live_cols:
            ch.old_columns = live_cols
    artifacts = codegen.generate_all(model_changes)

    # 6. Writeback 2 — PR comment (idempotent), plus artifacts on disk and
    # the step summary.
    body = pr_comment.render(report, contracts, artifacts, config.mode)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "comment.md").write_text(body)
    (out / "contract_payloads.json").write_text(json.dumps(
        [{"model": c.model_name, "mode": c.mode, "urn": c.urn,
          "payload": c.payload} for c in contracts], indent=2))
    for art in artifacts:
        (out / f"{art.view_name}.sql").write_text(art.sql)
        (out / f"{art.view_name}.yml").write_text(art.schema_yml)
    print(f"[guardian] artifacts written to {out}/")

    pr_comment.write_step_summary(body)
    if not args.no_post and config.github_token and config.github_repository:
        try:
            url = pr_comment.post_comment(config.github_repository,
                                          args.pr_number, body,
                                          config.github_token)
            print(f"[guardian] comment posted: {url}")
        except Exception as exc:
            print(f"[guardian] comment post failed ({exc}); "
                  "body is in the step summary")
    elif args.no_post:
        print("[guardian] --no-post: comment rendered but not posted")

    if args.strict and report.severity in ("HIGH", "CRITICAL"):
        return 2
    return 0


def main() -> None:
    sys.exit(run(parse_args()))


if __name__ == "__main__":
    main()
