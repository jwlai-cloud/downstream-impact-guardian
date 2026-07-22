"""Writeback #2: the PR comment. Renders one idempotent comment (updated in
place on synchronize) and mirrors the body to $GITHUB_STEP_SUMMARY so output
is visible even when the token can't post (fork PRs)."""
from __future__ import annotations

import json
import os

import requests

from agent.models import CompatArtifact, ContractResult, ImpactReport

MARKER = "<!-- downstream-impact-guardian -->"
SEVERITY_EMOJI = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}


def render(report: ImpactReport, contracts: list[ContractResult],
           artifacts: list[CompatArtifact], mode: str) -> str:
    lines = [MARKER, ""]
    lines.append(f"## {SEVERITY_EMOJI[report.severity]} Downstream Impact "
                 f"Guardian — **{report.severity}** (score {report.score})")
    if mode == "offline":
        lines.append("> ⚠️ Ran in **offline fixture mode** (no DataHub "
                     "credentials in this run). Lineage/query data below "
                     "comes from committed fixtures; on the maintainer's "
                     "instance this runs live.")
    lines += ["", report.narrative, ""]

    if report.model_changes:
        lines += ["### What changed", "",
                  "| Model | Change | Details |", "|---|---|---|"]
        for ch in report.model_changes:
            details = []
            if ch.renames:
                details += [f"`{o}` → `{n}`" for o, n in ch.renames]
            removed = [c.name for c in ch.columns if c.change == "removed"
                       and c.name not in {o for o, _ in ch.renames}]
            added = [c.name for c in ch.columns if c.change == "added"
                     and c.name not in {n for _, n in ch.renames}]
            if removed:
                details.append("removed: " + ", ".join(f"`{c}`" for c in removed))
            if added:
                details.append("added: " + ", ".join(f"`{c}`" for c in added))
            if "logic" in ch.kinds:
                if ch.changed_expressions:
                    details.append("logic changed in: " + ", ".join(
                        f"`{c}`" for c in ch.changed_expressions))
                else:
                    details.append("SQL logic modified (filters/joins/shape)")
            if "removed" in ch.kinds:
                details.append("**model deleted in this PR**")
            lines.append(f"| `{ch.model_name}` | "
                         f"{' + '.join(sorted(ch.kinds))} | "
                         f"{'; '.join(details)} |")
        lines.append("")

    any_consumers = any(report.consumers.get(ch.model_name)
                        for ch in report.model_changes)
    if any_consumers:
        lines += ["### Blast radius (from DataHub lineage — live systems, "
                  "not this repo)", "",
                  "| Downstream consumer | Platform | Type | Hops |",
                  "|---|---|---|---|"]
        all_consumers = sorted(
            (c for ch in report.model_changes
             for c in report.consumers.get(ch.model_name, [])),
            key=lambda c: c.hops)
        seen: set[tuple] = set()
        for c in all_consumers:
            key = (c.name, c.platform, c.entity_type)
            if key in seen:
                continue  # same entity reachable from several changed models
            seen.add(key)
            lines.append(f"| {c.name} | {c.platform} | "
                         f"{c.entity_type} | {c.hops} |")
        lines.append("")

    broken_queries = [(m, q) for m, qs in report.queries.items()
                      for q in qs if q.references_changed_column]
    if broken_queries:
        lines += ["### Queries that WILL break", "",
                  "These are real queries DataHub has observed against the "
                  "old columns:", ""]
        for model, q in broken_queries:
            who = f" — {q.user}" if q.user else ""
            src = f" ({q.platform})" if q.platform else ""
            lines += [f"**on `{model}`**{who}{src}:", "```sql",
                      q.sql.strip(), "```", ""]

    if report.glossary_changes or report.suspected_drifts:
        lines += ["### Semantic drift (DataHub glossary)", ""]
        for g in report.glossary_changes:
            lines += [f"**{g.term_name}**",
                      f"- DataHub (current business meaning): "
                      f"{g.live_definition}",
                      f"- This PR proposes: {g.proposed_definition}", ""]
        for s in (report.suspected_drifts or []):
            lines += [f"**{s.term_name}** — ⚠️ suspected",
                      f"- `{s.model_name}.{s.column}` is bound to this term "
                      f"and its logic changed, but this PR does not update "
                      f"the term's definition.",
                      f"- DataHub (current business meaning): "
                      f"{s.live_definition}",
                      f"- Verify the definition still holds — or update the "
                      f"glossary in this PR.", ""]

    lines += ["### Writeback 1 — Data Contracts in DataHub", ""]
    if not contracts:
        lines.append("ℹ️ No impacted model with known consumers — no "
                     "contract proposed.")
    for contract in contracts:
        prefix = f"**`{contract.model_name}`** — " if contract.model_name else ""
        if contract.urn:
            lines.append(f"{'✅' if contract.mode == 'upserted' else '☑️'} "
                         f"{prefix}contract `{contract.urn}` written "
                         f"({contract.mode}), status **PROPOSED** — "
                         f"approving it = merging this PR after adopting "
                         f"the compatibility code.")
            if contract.note:
                lines.append(f"> {contract.note}")
        else:
            lines.append(f"ℹ️ {prefix}{contract.note}")
            lines += ["", f"<details><summary>Contract payload for "
                      f"`{contract.model_name}`</summary>", "", "```json",
                      json.dumps(contract.payload, indent=2), "```",
                      "</details>", ""]
    lines.append("")

    if artifacts:
        lines += ["### Writeback 2 — generated compatibility code "
                  "(mergeable)", ""]
        for art in artifacts:
            flag = (" ⚠️ **needs human attention** (unmappable pieces are "
                    "marked in the SQL)" if art.requires_human else "")
            lines += [f"**`models/compat/{art.view_name}.sql`**{flag}",
                      "```sql", art.sql.rstrip(), "```", "",
                      f"**`models/compat/{art.view_name}.yml`**",
                      "```yaml", art.schema_yml.rstrip(), "```", ""]
        lines.append("Drop these files into `models/compat/`, run "
                     "`dbt build --select " +
                     " ".join(a.view_name for a in artifacts) +
                     "`, and downstream consumers keep working while they "
                     "migrate.")
    lines.append("")
    lines.append("---")
    lines.append("_Generated by [Downstream Impact Guardian]"
                 "(https://github.com/" +
                 os.environ.get("GITHUB_REPOSITORY", "junwei-lai/downstream-impact-guardian")
                 + ") · reads DataHub for what's live, the PR for what's "
                 "proposed · never ingests hypothetical state._")
    return "\n".join(lines)


def post_comment(repo: str, pr_number: int, body: str, token: str) -> str:
    """Create or update the guardian's single comment. Returns the comment
    URL, or raises."""
    headers = {"Authorization": f"Bearer {token}",
               "Accept": "application/vnd.github+json"}
    base = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    existing = requests.get(base, headers=headers, timeout=30)
    existing.raise_for_status()
    for c in existing.json():
        if MARKER in (c.get("body") or ""):
            resp = requests.patch(c["url"], headers=headers,
                                  json={"body": body}, timeout=30)
            resp.raise_for_status()
            return resp.json()["html_url"]
    resp = requests.post(base, headers=headers, json={"body": body},
                         timeout=30)
    resp.raise_for_status()
    return resp.json()["html_url"]


def write_step_summary(body: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a") as f:
            f.write(body + "\n")
