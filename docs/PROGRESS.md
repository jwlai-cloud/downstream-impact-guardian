# PROGRESS

Running log. Read this first when resuming; update at end of every session.

## Current state (2026-08-04)

**Everything is live and the last infrastructure surprise is closed.** Six days
to the Aug 10 submission deadline; the only remaining blockers are the video
upload and the Devpost form, both maintainer-side.

Session of 2026-08-04, in order:

- **DataHub survives a restart, proven not inferred.** Starting the instance
  brought the OS back with all seven containers `Exited (143)`: the quickstart
  ships **no restart policy**, so "instance running" and "every judge URL dead"
  were the same state — and Aug 17 would have gone the same way. Fixed by
  declaring `restart: unless-stopped` in
  [`scripts/dig-override.yml`](../scripts/dig-override.yml) (in the repo now,
  not only on the VM, so a rebuild can't reproduce it). A full stop/start cycle
  then reached both endpoints healthy in **~2 min with zero intervention**;
  judge token still authenticates, all 10 `fct_orders` entities intact.
- **Two bring-up cycles were lost to my own error**: `docker compose up -d`
  needs `--profile quickstart`, and without it starts kafka, **exits 0, and
  reports success** while nothing serves. That produced two wrong diagnoses
  (CPU-credit throttling, fail2ban) on a box that was idle at load 0.08. Both
  traps are now gotchas 5 and 6 in [`AWS_BRINGUP.md`](AWS_BRINGUP.md). One
  ~25-min SSH blackout remains **unexplained** — cleared by a stop/start, no
  root cause found; watch for it during judging.
- **Demo endpoint hardened** (PR #38): hitting a run cap was a dead end, so
  both 429s now return a `fallback` URL the page renders as a link to the
  workbench. `DEMO_MAX_RUNS_PER_DAY` failed **open** two ways — a typo gave
  `NaN` (`today >= NaN` always false, cap silently gone) and `|| 40` turned an
  explicit `0` into 40 — now fails closed with 503, covered by
  `api/quota-config.test.mjs`.
- **The 3-minute wait no longer reads as a hang**: `/api/status` reports the
  workflow's real step (`step 4/7`) from the Actions jobs API, plus an elapsed
  clock and an upfront expectation. Also fixed a live-run finding — a commit
  accumulates one check-run per attempt, so the page could show a judge a
  **stale failure** for a run that succeeded; `/api/status` now keeps only the
  newest per name.
- **The workbench was never stale** (an earlier claim of mine, wrong): all four
  linked runs are live-mode at 24/11/7/7, matching `JUDGING.md`. Only this
  repo's dogfood draft #5 was stale, and its re-run now reads live mode,
  CRITICAL 24, contract upserted.
- **Column-level lineage: measured, and it killed two earlier framings** — see
  step 3 below. Not "unread", not a coverage gap: the edges the "derived" rung
  needs do not exist in this catalog at all.
- Stale SSH rule (`125.253.50.30/32`, a home IP the ISP has since reassigned)
  revoked; only the current maintainer IP remains on port 22.

## Earlier state (2026-07-27)

**The judge-facing DataHub is deployed and permanent.** The last piece of
infrastructure risk is closed: no more ephemeral tunnels, no laptop-must-stay-awake.

- **AWS EC2 `t4g.large`** in the maintainer's personal account, `us-east-1`,
  with an **Elastic IP** (URL survives stop/start). ~$1.60/day running,
  ~$0.11/day stopped. Details + the hardening record in
  [`AWS_BRINGUP.md`](AWS_BRINGUP.md); cost rationale in
  [`DEPLOY_OPTIONS.md`](DEPLOY_OPTIONS.md).
- **Hardened before exposure**: default `datahub/datahub` disabled,
  `METADATA_SERVICE_AUTH_ENABLED=true` (anonymous API → 401), a `judge`
  account with **Reader** role (writes denied, verified), SSH restricted to
  one IP. Ports 8080/9002 were widened to the internet only after all of it.
- **Catalog populated**: dbt models + lineage + assertions, glossary,
  6 cross-team consumers with ownership, the `depends_on_columns`
  declaration, 3 observed queries.
- **End-to-end verified against it** (PR #16 on the consumer repo):
  `mode=live` · CRITICAL 24 · Agent Context Kit · real Qwen narrative ·
  both contracts `upserted` · Slack alert sent · comment posted.
- **Judge routes documented** in [`JUDGING.md`](JUDGING.md) — four routes in
  effort order plus a criterion→evidence map. Credentials live only in the
  maintainer's `~/dig-datahub-credentials.txt` and the Devpost private
  submission description (the form has no private field), never in this repo.

**Next, in priority order:**
1. ~~Start the instance before judging opens.~~ **DONE 2026-08-04** — running,
   both endpoints healthy, and restarting is now unattended (~2 min), so it can
   be stopped again until ~Aug 16 to save ~$18 with no bring-up ritual.
2. ~~Re-trigger the standing demo PRs.~~ **DONE 2026-08-04.** The four
   workbench runs turned out **not** to be stale — all live-mode at 24/11/7/7,
   matching `JUDGING.md`. Only this repo's dogfood draft #5 carried the old
   *offline fixture, score 22*; its re-run now reads **live mode, CRITICAL 24,
   contract upserted**, so every artifact agrees.
3. ~~Verify what column-level lineage the instance actually holds.~~
   **DONE 2026-08-04 — answered, and the answer changes the claim.** Queried
   every model on the live instance (GraphQL rejects the `aspects` signature
   used in the old snippet below; the OpenAPI v3 aspect read works):

   ```bash
   URN='urn:li:dataset:(urn:li:dataPlatform:bigquery,agent-era.fiction_retail.revenue_daily,PROD)'
   E=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "$URN")
   curl -s "$DATAHUB_GMS_URL/openapi/v3/entity/dataset/$E?aspects=upstreamLineage" \
     -H "Authorization: Bearer $DATAHUB_GMS_TOKEN"
   ```

   | Dataset | table upstreams | column edges |
   |---|---|---|
   | `dbt:fct_orders` | 2 | **0** |
   | `dbt:stg_orders` | 1 | **0** |
   | `dbt:revenue_daily` | 1 | **0** |
   | `bigquery:fct_orders` | 1 | 8 |
   | `bigquery:stg_orders` | 1 | 6 |
   | `bigquery:revenue_daily` | 1 | 4 |

   The dbt nodes hold **no** column edges, and the BigQuery ones hold only
   **sibling identity mappings** — `dbt:revenue_daily.gross_revenue →
   bigquery:revenue_daily.gross_revenue`, 4 of 4, every column to itself.
   There is **no model→model column lineage anywhere in this instance**.

   So `include_column_lineage=True` is real but doesn't mean what it sounds
   like here: it maps a dbt node onto its warehouse sibling, not
   `fct_orders.order_total → revenue_daily.gross_revenue`. Reading the
   "derived" rung today would therefore buy **nothing** — not a coverage gap
   to be filled by more ingestion, but an absence of the edge type the rung
   needs. Cross-model column edges would require dbt's own compiled-SQL
   column info or a BigQuery lineage/usage source. The worst-case bound plus
   `depends_on_columns` declarations remain the only honest inputs, which is
   what the shipped precision ladder already does.
4. Fill the **Devpost form** from [`SUBMISSION.md`](SUBMISSION.md) — the
   Additional-info and Feedback-Prize answers are in its appendix. Note the
   form has **no private free-text field** for credentials, so the judge login
   (Reader-only), read-only token and demo access code go in the public
   description; the admin password never leaves
   `~/dig-datahub-credentials.txt`.
5. Set a **spend cap** on the Qwen/DashScope key — every triggered run makes
   a paid LLM call.
6. Tag `v1` at submission freeze.
7. **After Aug 31, at teardown:** terminate the instance, **release the
   Elastic IP**, delete the `dig-ec2-deploy` IAM inline policy — and
   **remove the live-catalog links** from `site/index.html` and the demo UI
   footer. AWS recycles released IPs, so leaving them in place would point
   the repo at a stranger's server.
8. Optional: align the SUBMISSION appendix shot list to the v6 cut (~2:57).

## Earlier state (2026-07-24)

**Core loop: DONE, proven live, and narrated by a real LLM.** The four
standing demo PRs on the consumer repo (`fiction-retail-dbt`, all draft) run
in live mode without the offline banner, narrated by a **real
`openai/qwen3.6-flash` call** on Alibaba DashScope. A representative real run
reports `severity=CRITICAL score=24`, both contracts `upserted`, narrative
attributed to the model, comment posted. The live path (DataHub lineage,
glossary drift, `upsertDataContract` + PENDING status aspect) is verified
against a real self-hosted OSS quickstart with real BigQuery data
(`agent-era`). 48 unit tests, no network.

Done, in order:
- All design questions resolved across two grill sessions (docs/adr/0001–0009,
  CONTEXT.md glossary, docs/SPEC.md §11–12).
- dbt fiction-retail demo project + committed prod manifest + ingestion
  recipes; one-shot `scripts/ingest_all.sh` (verified green).
- Agent pipeline: 3-source detection (schema manifest diff, sqlglot metric
  drift, glossary semantic drift), sibling-aware DataHub client
  (live + fixture), deterministic blast-radius scoring, contract-per-impacted-model
  writeback, compat/legacy codegen, idempotent PR comment. 48 unit tests.
- Packaging: reusable composite action (`action.yml`), dogfooded by this
  repo; ADK narrative reads via DataHub Agent Context Kit; `.mcp.json`
  interactive surface via `mcp-server-datahub`.
- Published: master PR-protected; PR #2 (action env/injection fixes)
  reviewed by 3 bots, all comments addressed, merged; demo PR re-triggered
  and green.
- Submission collateral: docs/SUBMISSION.md draft (Devpost sections + video
  script), the design blog (docs/blog/2026-07-23), a media-ready launch post
  (docs/blog/launch-post.md), and an interactive engineering tutorial
  ("how it's built"): https://claude.ai/code/artifact/c578039e-bce6-4330-8396-cb48b739e7c6
- Demo video: final cut locked (~2:57).
- Narrative honesty + resilience: real LLM call every configured run, 3×
  retry with backoff, labeled template + `> [!WARNING]` banner on genuine
  failure, configured-but-keyless fails the check, noisy ADK default-value
  warning suppressed in the log.
- Slack stakeholder alerts documented (opt-in, HIGH/CRITICAL only,
  fire-and-forget via `slack-webhook-url`).

## Next (priority order)

1. **Permanent judge-facing DataHub instance — pick a row from
   docs/DEPLOY_OPTIONS.md** (AWS demoted — $65 judged too expensive). Menu:
   Hetzner CAX31 (~$16 total, recommended), Oracle Always Free ($0,
   credit-card retry), local Mac + Cloudflare Tunnel ($0, fragile), GCE/AWS
   (~$65, credits-only), or no instance (video+repo evidence — rules permit).
   Cloud trials verified sales-gated. The live-mode demos currently run
   through a throwaway localtunnel to the local quickstart; that needs to
   become a standing box that soaks before the Aug 17–31 judging window.
   Once any box exists: `scripts/oracle_vm_setup.sh` (any Ubuntu host) →
   harden → `scripts/ingest_all.sh` → `scripts/seed_demo_consumers.py` →
   repo secrets → demo PRs rerun live. Resolve by ~2026-08-10 so it soaks.
2. **Devpost submission form** — fill from docs/SUBMISSION.md; measure the
   `[MEASURE]` Action latency (last real run: ~45 s end-to-end, re-measure
   in live mode) and drop the final video in.
3. **Rotate the Slack webhook** that was exposed earlier — mint a fresh
   incoming webhook and reset the `SLACK_WEBHOOK_URL` secret on both repos.

## Open questions

- Which DEPLOY_OPTIONS.md row for the permanent instance — resolve by
  ~2026-08-10 so it soaks before the Aug 17–31 judging window (Hetzner
  recommended; soak-from-Aug-16 trims any paid row ~30%).
- ~~Column-level lineage (the "derived" rung) is **unread, not unavailable**.~~
  **RESOLVED 2026-08-04 by querying the live instance** (table in step 3
  above). Both earlier framings were wrong: it is not merely "unread", and
  the limitation is not *coverage*. The dbt nodes hold **zero** column edges;
  the BigQuery siblings hold only **identity mappings** of each dbt column
  onto its own warehouse column. No `fct_orders.order_total →
  revenue_daily.gross_revenue` edge exists on any entity here, so wiring
  `fineGrainedLineages` into `datahub_client.py` would return nothing usable
  — the rung has no data to stand on, rather than data we declined to read.
  **Scope this claim carefully when repeating it:** DataHub models and renders
  column-level lineage fine (the hackathon kickoff demo shows it in the UI for
  sample datasets). The gap is *this* dbt + BigQuery ingestion path, not the
  product.
  Cross-model column edges need dbt's compiled-SQL column info or a BigQuery
  lineage/usage source; neither is in scope before the deadline. The shipped
  ladder (declared `depends_on_columns` > worst-case bound) is therefore not
  a shortcut — it is the only honest option available on this instance.

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
variants, DataHub lineage/glossary/schema, workbench, button page,
PR #5 SAFE-row shot. VO COMPLETE: 13 beats generated via OpenAI TTS
(gpt-4o-mini-tts, onyx), ~201s raw -> ~2:55 at 1.15x; script covers
pain-point opening, three detectors (sqlglot named), advisory+Slack,
ladder+SAFE, agent edge (tool-verified synthesis + ranked actions),
template-without-key trust line.

Narrative honesty shipped (#22 + consumer #6, both merged): validation
matrix (configured model + missing key FAILS the check with the exact
secret to add; live-mode only — fork offline stays first-class),
::error:: annotations on runtime LLM failure, comment attributes its
writer (model id vs "no narrative LLM configured"), docs reframed
real-LLM-first. Provider = repo config: GUARDIAN_NARRATIVE_MODEL +
OPENAI_BASE_URL vars + OPENAI_API_KEY secret set on both repos (Qwen
flash). Blog gained §6 "Live-mode day" (tunnel, seeding,
skipCache bug, honesty protocol, SAFE staging).

Competitor recon (ForgetOps, submitted): zero LLM agents — pure
deterministic loop; validates our invariants, leaves us differentiated
on the real tool-using agent. Tactics adopted: Pages workbench (live),
JUDGING.md pending. Remaining: verify first Qwen-attributed run (fresh
runs only — gh run rerun replays old workflow snapshots), diagram
slides + Slack mock, motion captures, assembly, JUDGING.md, DataHub
docs-fix PR (bonus). User-side: deploy row by ~Aug 10, Devpost form.

## Session log (2026-07-24)

Video **v4 locked** (~2:57) at captures/video/dig-demo-v4.mp4 — final cut.
First Qwen-attributed live run verified: `severity=CRITICAL score=24`, both
contracts `upserted`, `narrative source: openai/qwen3.6-flash`, comment
posted. Merged on the way here: transient GMS gateway retry (502/503/504,
dropped conns), narrative retry (3× backoff, 180s per attempt) + prominent
`> [!WARNING]` fallback banner, and log hygiene — the noisy ADK "Default
value is not supported…for Google AI" warning is now filtered out.

Docs refreshed this session (branch `chore/log-hygiene-and-slack-docs`,
PR #29): ARCHITECTURE/LEARNING/PROGRESS + README synced to current state,
Slack alerting documented in the README, launch post added
(docs/blog/launch-post.md), interactive tutorial linked, test count
corrected to **48** everywhere, the old related-work comparison removed
(replaced with the problem stated directly), dataset-provenance note
added (custom dbt-shaped fiction-retail, not the DataHub SQLite sample).

Remaining, user-side: permanent DataHub box (deploy row by ~2026-08-10 so it
soaks before Aug 17–31), Devpost form, and rotating the exposed Slack
webhook secret.
