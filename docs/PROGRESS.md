# PROGRESS

Running log. Read this first when resuming; update at end of every session.

## Current state (2026-07-22)

**Core loop: DONE and proven on real infrastructure.** The standing demo
PR (#5, draft — replaces #1 after its accidental merge + revert) carries
a guardian report posted by the actual GitHub Action —
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
  reviewed by 3 bots, all comments addressed, merged; demo PR re-triggered
  and green.
- Submission collateral: docs/SUBMISSION.md draft (Devpost sections +
  Pinterest related-work comparison + video "edge" segment), two Claude
  artifacts (build summary, how-it-works).

## Next (priority order)

1. **Judge-facing DataHub instance — pick a row from
   docs/DEPLOY_OPTIONS.md** (2026-07-23; AWS demoted — $65 judged too
   expensive). Menu: Hetzner CAX31 (~$16 total, recommended), Oracle
   Always Free ($0, credit-card retry), local Mac + Cloudflare Tunnel
   ($0, fragile), GCE/AWS (~$65, credits-only), or no instance
   (video+repo evidence — rules permit). Cloud trials verified
   sales-gated 2026-07-22. Once any box exists:
   `scripts/oracle_vm_setup.sh` (any Ubuntu host) → harden →
   `scripts/ingest_all.sh` → repo secrets → demo PRs rerun live.
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
- Which DEPLOY_OPTIONS.md row — resolve by ~Aug 10 so the instance
  soaks before the Aug 17–31 judging window (Hetzner recommended;
  soak-from-Aug-16 trims any paid row ~30%).

## Incident log (2026-07-22)

Demo PR #1 was accidentally merged minutes after its check went green,
putting the staged breaking state onto master. Caught the same hour by the
brand-new `tests.yml` — the unit suite failed on PR #3's merge ref because
master's glossary now drifted against the fixtures. Reverted via PR #4;
demo recreated as **draft** PR #5 (drafts cannot be merged). Lesson
encoded: the standing demo PR stays a draft forever.

## Session log (2026-07-22, day 2)

Shipped and merged: deleted-model detection (a removed model was previously
invisible — now breaking + every observed query counted + `*_legacy` view;
three CodeRabbit review rounds), reusable-action portability fix
(cross-repo pip-cache bug found by the consumer repo's first run), the
one-button Vercel demo UI (XSS-hardened: bot-author check + DOMPurify),
living docs + tests CI. Awaiting merge: #10 per-column expression
attribution (sqlglot), #11 narrative model providers (Gemini default,
OpenAI/Qwen via LiteLLM).

Demo surface now: consumer repo `fiction-retail-dbt` with three standing
draft PRs — rename+drift+glossary (CRITICAL 22), whole-model deletion
(CRITICAL 10), silent metric drift with suspected semantic drift (HIGH 6)
— all produced by the PUBLISHED action cross-repo. Repo protections
applied across all hackathon repos.

Still user-blocked: PAT + Vercel import (button demo go-live), Oracle
credit-card retry (judge instance; Cloud trials verified sales-gated),
OpenAI/Qwen key as repo secret (narrative live), then filming.

## Session log (2026-07-23)

Merged #10–#13 (expression attribution, narrative model providers, docs,
stakeholder protocol incl. 8-finding CodeRabbit round with one real
aggregation bug). PR #14 open: declared column dependencies — the SAFE
verdict (fact-based per-consumer impact from consumers' own
depends_on_columns meta; tolerant custom-property parser; fixtures demo
BROKEN-as-fact and SAFE). Blog drafted: docs/blog/2026-07-23 (design
story in engineer voice). Artifacts refreshed. Remaining unchanged:
PAT+Vercel, Oracle retry, model keys + workflow wiring, filming.

## Session log (2026-07-23, night — live mode day)

Shipped and merged: deployment menu (DEPLOY_OPTIONS.md — AWS demoted,
Hetzner ~$16 recommended, organizer confirmed live URL not required),
GitHub Pages judge workbench (LIVE:
jwlai-cloud.github.io/downstream-impact-guardian — zero-credential
60-second route, ForgetOps-recon takeaway), Vercel button demo (LIVE:
downstream-impact-guardian.vercel.app — verified end-to-end, third
drift scenario added), captures/ gitignore, lineage skipCache fix +
scripts/seed_demo_consumers.py (#20).

Live mode achieved via user-run localtunnel to local quickstart: all
demo PRs now report WITHOUT the offline banner. Catalog seeded with the
mocked consumer layer (resolves the fixtures-vs-live open question);
found+fixed a real bug in the process (GMS searchAcrossLineage cache
made a freshly-seeded consumer invisible → skipCache). New standing
scenario 4 (fiction-retail-dbt #5): pure expression tweak → 🟢 SAFE
(declared) row live on camera. Narrative provider wiring: repo
variables GUARDIAN_NARRATIVE_MODEL/OPENAI_BASE_URL set (Qwen flash),
consumer PR #6 passes them through (awaiting merge).

Capture rig (Playwright) built: 24 stills incl. highlighted judge
variants, DataHub lineage/glossary/schema, workbench, button page. VO
script v3 (13 beats, 2:54): pain-point opening, sqlglot/YAML/ACK named,
advisory-not-blocking + Slack beat. Awaiting: .env with TTS key,
consumer PR #6 merge, then TTS + motion + assembly.
