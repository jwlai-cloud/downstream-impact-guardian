# ADR-0006: Prod dbt manifest committed at dbt_demo_project/prod_state/

Status: Accepted (2026-07-15)

## Context

`state:modified` semantics need a last-known-production manifest. The
workflow skeleton's TODO asked where it lives: Actions artifact from a
main-branch run, GCS, or committed to the repo. Judge-opened PRs must find
it with zero infrastructure.

Also decided here: CI never runs `dbt build` (it would execute against
BigQuery, which CI neither needs nor has credentials for). The PR side is
`dbt parse` (opens no connection); the diff itself is a Python
manifest-to-manifest comparison in `agent/dbt_state.py`, because codegen
needs *column-level* diffs that `dbt ls --select state:modified` (node
names only) cannot provide. Same artifacts, same semantics, richer output.

## Decision

Commit `prod_state/manifest.json`; refresh via
`scripts/refresh_prod_state.sh` on master merges that touch the dbt
project.

## Consequences

~600 KB of committed JSON and a manual refresh step a real product would
automate with a main-branch workflow — acceptable for the hackathon, and
the refresh script is the obvious seed of that automation. Deterministic
for anyone who clones the repo.
