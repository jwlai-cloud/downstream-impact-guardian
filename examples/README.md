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

This run used offline fixture mode (see ADR-0007), which is exactly what a
secrets-less fork PR produces; on the maintainer's DataHub instance the
same pipeline runs live.
