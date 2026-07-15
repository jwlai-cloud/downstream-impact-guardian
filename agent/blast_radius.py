"""Cross-system blast radius: the one judgment call only DataHub's graph can
inform (CLAUDE.md). Combines lineage + query history with the detected
changes into a scored ImpactReport."""
from __future__ import annotations

import re

from agent.models import (Consumer, GlossaryChange, ImpactReport, ModelChange,
                          QueryUsage)

# Scoring weights — deliberately simple and inspectable; the LLM narrates,
# it does not score (determinism in CI).
W_BREAKING_SCHEMA = 3
W_LOGIC_ON_GLOSSARY_METRIC = 2
W_LOGIC_PLAIN = 1
W_SEMANTIC_DRIFT = 2
W_PER_CONSUMER = 1
W_CONSUMER_CAP = 4
W_EXTERNAL_PLATFORM = 2
W_QUERY_HITS_CHANGED_COLUMN = 3

THRESHOLDS = [(9, "CRITICAL"), (6, "HIGH"), (3, "MEDIUM"), (0, "LOW")]


def _changed_column_names(change: ModelChange) -> set[str]:
    names = {c.name for c in change.columns if c.change in ("removed", "type_changed")}
    names |= {old for old, _ in change.renames}
    return names


def assess(model_changes: list[ModelChange],
           glossary_changes: list[GlossaryChange],
           consumers: dict[str, list[Consumer]],
           queries: dict[str, list[QueryUsage]]) -> ImpactReport:
    score = 0

    for change in model_changes:
        if change.breaking:
            score += W_BREAKING_SCHEMA
        if "logic" in change.kinds:
            score += W_LOGIC_PLAIN

        cs = consumers.get(change.model_name, [])
        score += min(len(cs) * W_PER_CONSUMER, W_CONSUMER_CAP)
        external = {c.platform for c in cs} - {"dbt", "bigquery"}
        score += len(external) * W_EXTERNAL_PLATFORM

        # Does any observed query in the wild reference a column this PR
        # removes or renames? That is a guaranteed break, not a maybe.
        changed_cols = _changed_column_names(change)
        for q in queries.get(change.model_name, []):
            hit = any(re.search(rf"\b{re.escape(col)}\b", q.sql, re.IGNORECASE)
                      for col in changed_cols)
            q.references_changed_column = hit
            if hit:
                score += W_QUERY_HITS_CHANGED_COLUMN

    score += len(glossary_changes) * W_SEMANTIC_DRIFT

    severity = next(label for floor, label in THRESHOLDS if score >= floor)
    report = ImpactReport(
        model_changes=model_changes,
        glossary_changes=glossary_changes,
        consumers=consumers,
        queries=queries,
        severity=severity,
        score=score,
    )
    report.narrative = _deterministic_narrative(report)
    return report


def _deterministic_narrative(r: ImpactReport) -> str:
    """Fallback narrative when no LLM is available (offline mode)."""
    parts = []
    for ch in r.model_changes:
        kinds = " + ".join(sorted(ch.kinds))
        n_cons = len(r.consumers.get(ch.model_name, []))
        breaking_qs = sum(1 for q in r.queries.get(ch.model_name, [])
                          if q.references_changed_column)
        s = f"`{ch.model_name}`: {kinds} change, {n_cons} downstream consumer(s)"
        if ch.renames:
            s += ", renames " + ", ".join(f"`{o}`→`{n}`" for o, n in ch.renames)
        if breaking_qs:
            s += (f"; {breaking_qs} observed production query/queries still "
                  f"reference the old column(s) — guaranteed breakage")
        parts.append(s + ".")
    for g in r.glossary_changes:
        parts.append(
            f"Semantic drift on glossary term **{g.term_name}**: the PR's "
            f"definition no longer matches what DataHub says the business "
            f"currently means by it.")
    return " ".join(parts) if parts else "No impactful changes detected."
