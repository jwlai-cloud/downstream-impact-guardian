# ADR-0004: Built-in Actions GITHUB_TOKEN, no PAT, no GitHub App

Status: Accepted (2026-07-15)

## Context

Open question framed this as fine-grained PAT vs GitHub App. Examining the
core loop dissolved it: the only GitHub write is posting/updating one PR
comment from inside the Action.

## Decision

The workflow's automatic `GITHUB_TOKEN` with `pull-requests: write` — zero
setup, scoped to the repo, rotated by GitHub. The PAT-vs-App question only
exists for the stretch-goal web UI (which creates branches/PRs from
outside Actions); decide it there if that gets built.

## Consequences

Fork PRs get a read-only token and cannot post comments — handled by
ADR-0007's step-summary mirror, and the documented judge path (PR from the
in-repo `demo/*` branch) doesn't hit it at all.
