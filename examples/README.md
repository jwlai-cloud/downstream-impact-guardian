# examples/

Real generated output, committed so judges can evaluate quality from this
folder alone, without running anything (per the hackathon rules'
recommendation).

Everything in `generated/` was produced by an actual run of
`python agent/main.py` against the `demo/breaking-change` branch diff —
not hand-written:

- `generated/comment.md` — the full PR comment (writeback #2): severity,
  what changed, cross-system blast radius from DataHub lineage, the two
  real queries that would break, semantic drift on the Gross Revenue
  glossary term, and both writebacks inline
- `generated/fct_orders_compat.sql` + `.yml` — mergeable backward-compat
  view mapping `order_amount_usd` back to `order_total`, reproducing the
  full live schema (sourced from DataHub, not just yml docs)
- `generated/revenue_daily_legacy.sql` + `.yml` — the pre-PR metric logic
  preserved verbatim, with its `ref()` retargeted at the compat view so it
  still compiles after the upstream rename
- `generated/contract_payload.json` — the exact Data Contract payload
  (writeback #1) bundling the dataset's ingested dbt-test assertions, with
  PROPOSED provenance

- `generated/contract_payloads.json` — one contract per impacted model
  (ADR-0009): `fct_orders` (breaking) and `revenue_daily` (drifted with
  known consumers)

The `generated/` run used offline fixture mode (see ADR-0007) — exactly
what a secrets-less fork PR produces, and the richer narrative since the
fixtures carry dashboards and observed queries.

`live-run/` is evidence from the same pipeline against a **real self-hosted
OSS DataHub** (2026-07-15): real lineage traversal, and a real
`upsertDataContract` — the contract urn in that comment exists in the
instance with `state: PENDING` and guardian provenance, verified via the
OpenAPI endpoint. Live lineage there has no Looker/query usage ingested
yet, which is why its blast radius is smaller than the fixture story.
