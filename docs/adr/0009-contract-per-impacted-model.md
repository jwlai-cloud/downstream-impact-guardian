# ADR-0009: One Data Contract per impacted model

Status: Accepted (2026-07-15, grill session 2)

## Context

The first implementation proposed a single contract per PR, targeting the
first breaking model. Stress scenario from the demo PR itself: `fct_orders`
breaks (rename) while `revenue_daily` drifts (refund exclusion) and feeds
the Monthly Board Pack — the board-facing metric drift left no durable
record in DataHub, only PR-comment prose.

## Decision

The guardian writes one contract per **impacted model**: any changed model
that is breaking OR has known consumers in DataHub lineage. Metric drift on
a consumed model is exactly the case where "the next person or agent
inherits the knowledge" matters. Volume stays trivial (a handful per PR at
most), so the GraphQL-mutations-are-low-volume caveat (SPEC §5) still
holds.

Related decisions from the same session, recorded here for the trail:
"breaking" stays schema-strict with **metric drift** as its own term, the
guardian adds a deterministic **suspected semantic drift** flag (term-bound
metric changed, glossary untouched), and the check stays **advisory**
(`--strict` opt-in). Vocabulary in `CONTEXT.md`.

## Consequences

Multiple contract results render in the PR comment (one line or payload
per model). A model with drift but zero known consumers gets no contract —
if nobody consumes it, there is nobody to protect, and the comment says so.
