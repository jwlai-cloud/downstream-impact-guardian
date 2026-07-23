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
    # Honest attribution: never let template text read as model prose, and
    # never let "configured but failed" read as "not configured".
    if report.narrative_source == "deterministic":
        attribution = ("_Summary compiled from the detected facts — no "
                       "narrative LLM configured (see README “Choosing the "
                       "narrative LLM”)._")
    elif report.narrative_source.startswith("failed:"):
        model = report.narrative_source.removeprefix("failed:")
        attribution = (f"_Narrative LLM call failed (`{model}` — see the "
                       "Action log); summary compiled from the detected "
                       "facts._")
    else:
        attribution = (f"_Narrative by `{report.narrative_source}` via "
                       "Google ADK + DataHub Agent Context Kit._")
    lines += ["", report.narrative, "", attribution, ""]

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
        lines += ["### Blast radius & who to inform (from DataHub lineage "
                  "+ ownership — live systems, not this repo)", "",
                  "| Downstream consumer | Platform | Type | Worst-case impact | "
                  "Stakeholders to inform |",
                  "|---|---|---|---|---|"]
        impact_badge = {"BROKEN": "🔴 BROKEN", "DISTORTED": "🟠 DISTORTED",
                        "ADVISORY": "🟡 ADVISORY",
                        "SAFE": "🟢 SAFE (declared)", "": "—"}
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
            owners = (", ".join(c.owners) if c.owners
                      else "⚠️ **unowned** — assign an owner in DataHub")
            lines.append(f"| {c.name} | {c.platform} | {c.entity_type} | "
                         f"{impact_badge.get(c.impact, c.impact)} | "
                         f"{owners} |")
        lines.append("")
        lines.append("> Impact is the honest upper bound from the upstream "
                     "change kind — except 🟢 SAFE rows, which are FACTS: "
                     "those consumers declared the columns they read "
                     "(`depends_on_columns` in their own dbt meta) and none "
                     "were touched. Declare yours to earn the same verdict; "
                     "column-level lineage will refine the rest.")
        lines.append("")

    # Column-level effects: per changed column, the EVIDENCE we hold today
    # (what happened to it, which observed queries name it, which glossary
    # term binds it). The column->consumer join needs column-level lineage
    # and stays roadmap; this section is facts, not worst-case.
    col_rows = []
    for ch in report.model_changes:
        col_events: dict[str, list[str]] = {}
        for old, new in ch.renames:
            col_events.setdefault(old, []).append(f"renamed → `{new}`")
        for c in ch.columns:
            if c.change == "removed" and c.name not in {o for o, _ in ch.renames}:
                col_events.setdefault(c.name, []).append("removed")
        for c in getattr(ch, "changed_expressions", []) or []:
            col_events.setdefault(c, []).append("expression changed")
        if "removed" in ch.kinds:
            for c in ch.old_columns:
                col_events.setdefault(c, []).append("model deleted")
        for col, events in col_events.items():
            import re as _re
            q_hits = [q for q in report.queries.get(ch.model_name, [])
                      if _re.search(rf"\b{_re.escape(col)}\b", q.sql,
                                    _re.IGNORECASE)]
            evidence = []
            if q_hits:
                evidence.append(f"{len(q_hits)} observed quer"
                                f"{'y' if len(q_hits) == 1 else 'ies'} "
                                "reference it")
            for s in (report.suspected_drifts or []):
                if s.model_name == ch.model_name and s.column == col:
                    evidence.append(f"bound to glossary term "
                                    f"**{s.term_name}**")
            col_rows.append(f"| `{ch.model_name}.{col}` | "
                            f"{'; '.join(events)} | "
                            f"{'; '.join(evidence) or '—'} |")
    if col_rows:
        lines += ["### Column-level effects (evidence held today)", "",
                  "| Column | What happened | Observed evidence |",
                  "|---|---|---|"]
        lines += col_rows
        lines += ["",
                  "> Which downstream consumers read each column needs "
                  "column-level lineage — roadmap. Everything above is "
                  "direct evidence, not inference.", ""]

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


def build_slack_payload(report: ImpactReport, pr_url: str) -> dict:
    """One summary message for HIGH/CRITICAL runs (ADR-0010)."""
    victims = []
    seen = set()
    for cs in report.consumers.values():
        for c in cs:
            key = c.urn or (c.name, c.platform, c.entity_type)
            if key in seen or not c.impact:
                continue
            seen.add(key)
            who = ", ".join(c.owners) if c.owners else "unowned"
            victims.append(f"• {c.impact}: {c.name} ({who})")
    text = (f":rotating_light: Downstream Impact Guardian — "
            f"*{report.severity}* (score {report.score})\n"
            f"{pr_url}\n" + "\n".join(victims[:10]))
    return {"text": text}


def notify_slack(report: ImpactReport, pr_url: str) -> None:
    """Fire-and-forget: never fails the check (ADR-0010)."""
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook or report.severity not in ("HIGH", "CRITICAL"):
        return
    try:
        resp = requests.post(webhook, json=build_slack_payload(
            report, pr_url), timeout=10)
        resp.raise_for_status()
        print("[guardian] slack notification sent")
    except Exception as exc:
        # never log exc details here — they can embed the webhook URL
        print(f"[guardian] slack notification failed (non-fatal): "
              f"{type(exc).__name__}")


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
