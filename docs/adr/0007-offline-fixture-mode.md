# ADR-0007: Offline fixture mode is a first-class agent mode

Status: Accepted (2026-07-15)

## Context

Fork PRs receive no repository secrets — an agent triggered from a fork can
reach neither DataHub nor Gemini and would produce nothing. Separately, the
whole pipeline had to be built and tested before any live DataHub instance
existed.

## Decision

`Config.from_env` resolves mode automatically: missing
`DATAHUB_GMS_URL`/`DATAHUB_GMS_TOKEN` ⇒ offline. Offline mode reads
committed `agent/fixtures/*.json` (lineage, queries, schemas, glossary,
assertions) shaped exactly like live responses, renders the complete
comment with a visible "offline fixture mode" banner, and always mirrors
the body to `$GITHUB_STEP_SUMMARY` (fork tokens can't post comments).
Deterministic scoring/codegen never depend on the LLM; the ADK narrative is
a live-mode enhancement that degrades silently.

The documented judge path avoids degradation entirely: open a PR from the
pre-made `demo/*` branch to `master` **within this repo** — public repos
let anyone with read access open a PR between existing branches, no fork
needed — and the run gets real secrets.

## Consequences

Every judge sees full output regardless of secrets; the 21-test suite runs
with no network; fixtures double as committed examples of DataHub's data
shapes. Cost: fixtures must stay consistent with the dbt project when the
demo scenario changes.
