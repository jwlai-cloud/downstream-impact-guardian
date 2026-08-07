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

`live-run/` is evidence from the same pipeline against the **real self-hosted
OSS DataHub** instance, refreshed 2026-08-04 from the run on this repo's own
`demo/breaking-change` PR (the project dogfoods its own action):

- `live-run/comment.md` — 🔴 **CRITICAL (score 24)**, with the blast radius
  read from live lineage: six cross-system consumers across three teams,
  including two **Looker dashboards** and three BigQuery datasets, plus the
  **two observed production queries** that still reference `order_total` —
  guaranteed breakage, not inferred. Both Data Contracts written back as
  **PROPOSED** (`urn:li:dataContract:b2ad38e5…`, `…b77b9bb4…`).
- `live-run/contract_payloads.json` — the contract payloads as emitted. Note
  the provenance: these are from the 2026-07-15 run, kept because the payload
  *shape* is what they illustrate; the urns in the current `comment.md` come
  from the newer run.

An earlier snapshot of this file showed 🟠 HIGH (score 8) with a single
consumer, because that instance predated seeding the cross-team consumers. It
was replaced rather than kept, so every artifact in this repo now agrees on the
same verdict — the workbench, the video, `docs/SUBMISSION.md`, and this folder.
