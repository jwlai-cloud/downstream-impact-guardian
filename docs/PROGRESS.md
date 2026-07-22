# PROGRESS

Running log. Read this first when resuming; update at end of every session.

## Current state (2026-07-22)

**Core loop: DONE and proven on real infrastructure.** The standing demo
PR (#1) carries a guardian report posted by the actual GitHub Action —
offline fixture mode, CRITICAL severity, both contract payloads recorded,
comment idempotent. The live path (DataHub lineage, glossary drift,
`upsertDataContract` + PENDING status aspect) is verified against a real
self-hosted OSS quickstart with real BigQuery data (`agent-era`).

Done, in order:
- All design questions resolved across two grill sessions (docs/adr/0001–0009,
  CONTEXT.md glossary, docs/SPEC.md §11–12).
- dbt fiction-retail demo project + committed prod manifest + ingestion
  recipes; one-shot `scripts/ingest_all.sh` (verified green).
- Agent pipeline: 3-source detection, sibling-aware DataHub client
  (live + fixture), deterministic blast-radius scoring, contract-per-impacted-model
  writeback, compat/legacy codegen, idempotent PR comment. 26 tests.
- Packaging: reusable composite action (`action.yml`), dogfooded by this
  repo; ADK narrative reads via DataHub Agent Context Kit; `.mcp.json`
  interactive surface via `mcp-server-datahub`.
- Published: master PR-protected; PR #2 (action env/injection fixes)
  reviewed by 3 bots, all comments addressed, merged; PR #1 re-triggered
  and green.
- Submission collateral: docs/SUBMISSION.md draft (Devpost sections +
  Pinterest related-work comparison + video "edge" segment), two Claude
  artifacts (build summary, how-it-works).

## Next (priority order)

1. **Judge-facing DataHub instance** — Oracle Always Free (signup blocked
   on debit card; needs a credit card retry) or GCE e2-standard-2 in
   `agent-era` (~$35, zero friction, everything scripted). Then:
   `scripts/oracle_vm_setup.sh` (works on any Ubuntu box) → harden →
   `scripts/ingest_all.sh` → repo secrets → PR #1 reruns in live mode.
2. **Gemini key** (`GOOGLE_API_KEY` secret) — exercises the ADK/ACK
   narrative path end-to-end; set a spend cap on the key when creating it.
3. **Demo video** (3 min) — script skeleton in docs/SUBMISSION.md appendix;
   use the hackathon-demo-video skill; record the PR-comment reveal + the
   DataHub lineage/contract screens.
4. **Devpost form** — fill from docs/SUBMISSION.md; measure the `[MEASURE]`
   Action latency (last real run: 45 s end-to-end, re-measure in live mode).
5. Stretch only after all above: `tools/demo_ui/` (Vercel free).

## Open questions

- ADK narrative call has **no explicit timeout** around `asyncio.run` in
  `agent/adk_agent.py` — a hung Gemini call would stall the Action until
  the job timeout. Add a bounded timeout when the live key exists to test
  against. (Low risk: narrative is best-effort by design.)
- `pluginUsage`-style question for judges: does live lineage need query
  usage + a Looker layer ingested, or do fixtures carry that story? Decide
  when the judge instance is up (docs/ARCHITECTURE.md "live-mode gaps").
- Oracle vs GCE — resolve by ~Aug 10 so the instance soaks before the
  Aug 17–31 judging window.
