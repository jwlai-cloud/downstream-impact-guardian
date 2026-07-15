# ADR-0002: Compat artifact = dbt views + tests, generated deterministically

Status: Accepted (2026-07-15)

## Context

Open question: SQL view vs dbt macro vs both. Also undecided: should an LLM
author the merged code?

## Decision

Two deterministic template families, no macro:

- **`<model>_compat` view** for schema changes — re-exposes the old column
  contract (renames mapped back, e.g. `order_amount_usd as order_total`).
  The old shape is sourced from DataHub's live schema (the authority on
  what consumers actually see), with manifest columns as fallback.
- **`<model>_legacy` view** for logic-only changes — carries the pre-PR SQL
  verbatim, with `ref()`s retargeted at sibling compat views so it still
  compiles after upstream renames in the same PR.

Both ship with a schema.yml (description + tests). The LLM (ADK/Gemini)
writes the impact *narrative*, never the merged code: templates guarantee
valid dbt SQL for the supported change classes, and unmappable cases
(column removed with no replacement) are flagged `requires_human` instead
of guessed at.

## Consequences

Codegen is unit-testable and cannot hallucinate. A macro would generalize
across many tables but is over-engineered for one staged change and harder
for judges to evaluate at a glance. Change classes outside
rename/remove/logic produce a flagged draft, not silent wrong code.
