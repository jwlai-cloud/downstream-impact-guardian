"""Cross-system blast radius: the one judgment call only DataHub's graph can
inform (CLAUDE.md). Combines lineage + query history with the detected
changes into a scored ImpactReport."""
from __future__ import annotations

import re

from agent.models import (Consumer, GlossaryChange, ImpactReport, ModelChange,
                          QueryUsage, SuspectedDrift)

# Scoring weights — deliberately simple and inspectable; the LLM narrates,
# it does not score (determinism in CI).
W_BREAKING_SCHEMA = 3
W_LOGIC_ON_GLOSSARY_METRIC = 2
W_LOGIC_PLAIN = 1
W_SEMANTIC_DRIFT = 2
W_SUSPECTED_DRIFT = 1   # suspicion, not asserted divergence — weighs less
W_PER_CONSUMER = 1
W_CONSUMER_CAP = 4
W_EXTERNAL_PLATFORM = 2
W_QUERY_HITS_CHANGED_COLUMN = 3

THRESHOLDS = [(9, "CRITICAL"), (6, "HIGH"), (3, "MEDIUM"), (0, "LOW")]


def _changed_column_names(change: ModelChange) -> set[str]:
    names = {c.name for c in change.columns if c.change in ("removed", "type_changed")}
    names |= {old for old, _ in change.renames}
    return names


def classify_impact(change: ModelChange) -> str:
    """Per-consumer impact level (ADR-0010), worst-applicable-wins, derived
    from the upstream change kind. Column-level lineage would refine this
    per consumer; until then worst-case is the honest call."""
    if change.breaking:          # removed model, or removed/renamed columns
        return "BROKEN"
    if "logic" in change.kinds:
        return "DISTORTED"
    return "ADVISORY"


def classify_declared_impact(change: ModelChange,
                             declared: list[str]) -> str:
    """Fact-based impact for a consumer that DECLARED its columns on this
    model (ADR-0010 addendum). Verdicts here are facts, not upper bounds:
    - model deleted -> BROKEN (the relation itself is gone)
    - declared ∩ removed/renamed columns -> BROKEN
    - filter/join logic change -> DISTORTED (every column's values move —
      a declaration cannot clear it)
    - expression change intersecting declared -> DISTORTED
    - otherwise -> SAFE"""
    if "removed" in change.kinds:
        return "BROKEN"
    declared_set = {d.lower() for d in declared}
    if declared_set & {c.lower() for c in _changed_column_names(change)}:
        return "BROKEN"
    if "logic" in change.kinds:
        exprs = {c.lower() for c in change.changed_expressions}
        if not exprs:                # filters/joins: values move everywhere
            return "DISTORTED"
        if declared_set & exprs:
            return "DISTORTED"
    return "SAFE"


def assess(model_changes: list[ModelChange],
           glossary_changes: list[GlossaryChange],
           consumers: dict[str, list[Consumer]],
           queries: dict[str, list[QueryUsage]],
           suspected_drifts: list[SuspectedDrift] | None = None) -> ImpactReport:
    suspected_drifts = suspected_drifts or []
    score = 0

    for change in model_changes:
        if change.breaking:
            score += W_BREAKING_SCHEMA
        if "logic" in change.kinds:
            score += W_LOGIC_PLAIN

        cs = consumers.get(change.model_name, [])
        worst_case = classify_impact(change)
        order = {"": 0, "SAFE": 1, "ADVISORY": 2, "DISTORTED": 3, "BROKEN": 4}
        for c in cs:
            declared = c.declared_deps.get(change.model_name)
            impact = (classify_declared_impact(change, declared)
                      if declared is not None else worst_case)
            if order[impact] > order.get(c.impact, 0):
                c.impact = impact
        score += min(len(cs) * W_PER_CONSUMER, W_CONSUMER_CAP)
        external = {c.platform for c in cs} - {"dbt", "bigquery"}
        score += len(external) * W_EXTERNAL_PLATFORM

        # Does any observed query in the wild reference a column this PR
        # removes or renames? That is a guaranteed break, not a maybe.
        # A DELETED model breaks every query against it unconditionally —
        # column-token matching would miss `SELECT *` / `COUNT(*)`.
        changed_cols = _changed_column_names(change)
        for q in queries.get(change.model_name, []):
            hit = ("removed" in change.kinds or
                   any(re.search(rf"\b{re.escape(col)}\b", q.sql, re.IGNORECASE)
                       for col in changed_cols))
            q.references_changed_column = hit
            if hit:
                score += W_QUERY_HITS_CHANGED_COLUMN

    # Worst-wins across INSTANCES: main.py fetches consumers per changed
    # model, so the same entity appears as distinct objects. Aggregate by
    # stable identity (urn, else name/platform/type), take max impact,
    # union owners, and write back to every instance so any survivor of
    # downstream dedup carries the correct verdict.
    order = {"": 0, "SAFE": 1, "ADVISORY": 2, "DISTORTED": 3, "BROKEN": 4}
    by_key: dict[tuple, list[Consumer]] = {}
    for cs in consumers.values():
        for c in cs:
            key = (c.urn,) if c.urn else (c.name, c.platform, c.entity_type)
            by_key.setdefault(key, []).append(c)
    for instances in by_key.values():
        worst = max((i.impact for i in instances), key=lambda v: order.get(v, 0))
        owners = sorted({o for i in instances for o in i.owners})
        for i in instances:
            i.impact = worst
            i.owners = owners

    score += len(glossary_changes) * W_SEMANTIC_DRIFT
    score += len(suspected_drifts) * W_SUSPECTED_DRIFT

    severity = next(label for floor, label in THRESHOLDS if score >= floor)
    report = ImpactReport(
        model_changes=model_changes,
        glossary_changes=glossary_changes,
        consumers=consumers,
        queries=queries,
        suspected_drifts=suspected_drifts,
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
        s = (f"`{ch.model_name}`: MODEL DELETED, {n_cons} downstream consumer(s)"
             if "removed" in ch.kinds else
             f"`{ch.model_name}`: {kinds} change, {n_cons} downstream consumer(s)")
        if ch.renames:
            s += ", renames " + ", ".join(f"`{o}`→`{n}`" for o, n in ch.renames)
        if ch.changed_expressions:
            s += (", expression changed for " +
                  ", ".join(f"`{c}`" for c in ch.changed_expressions))
        if breaking_qs:
            s += (f"; {breaking_qs} observed production query/queries still "
                  f"reference the old column(s) — guaranteed breakage")
        parts.append(s + ".")
    for g in r.glossary_changes:
        parts.append(
            f"Semantic drift on glossary term **{g.term_name}**: the PR's "
            f"definition no longer matches what DataHub says the business "
            f"currently means by it.")
    for s in (r.suspected_drifts or []):
        parts.append(
            f"Suspected semantic drift: `{s.model_name}.{s.column}` is bound "
            f"to glossary term **{s.term_name}** and its logic changed, but "
            f"this PR does not update the term — verify the live definition "
            f"still holds.")
    return " ".join(parts) if parts else "No impactful changes detected."
