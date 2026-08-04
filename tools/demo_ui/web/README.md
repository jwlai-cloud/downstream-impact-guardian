# demo_ui/web — the one-button judge demo (Vercel)

Static page + two serverless functions. A click opens a real PR with a
staged breaking change against the consumer repo
([fiction-retail-dbt](https://github.com/jwlai-cloud/fiction-retail-dbt)),
polls the guardian Action, and renders the report inline.

## Deploy (once, ~5 min)

1. Create a **fine-grained PAT** scoped to ONLY `jwlai-cloud/fiction-retail-dbt`:
   Repository permissions → Contents: Read+Write, Pull requests: Read+Write.
   Expiry: Sep 1. (Blast radius if leaked = one demo repo.)
2. Vercel → New Project → import `downstream-impact-guardian` →
   **Root Directory: `tools/demo_ui/web`** → Framework preset: Other.
3. Environment variables (Production scope):

   | Name | Required | Default | Notes |
   |---|---|---|---|
   | `GITHUB_TOKEN` | **yes** | — | the PAT from step 1 |
   | `DEMO_ACCESS_CODE` | **while the gate is on** | — | gate on with this unset serves 503 to everyone, by design |
   | `DEMO_GATE` | no | **on** | only `off`/`false`/`0`/`no` disables it; anything else, including a typo, keeps it on |
   | `DEMO_MAX_RUNS_PER_DAY` | no | `40` | rolling-24h cap |
   | `GH_OWNER` / `GH_REPO` | no | `jwlai-cloud` / `fiction-retail-dbt` | |

   Env changes need a redeploy to take effect. Check which way the gate is
   pointing with `curl .../api/create-demo` → `{"gated":true|false}`.
4. Deploy. The URL becomes the Devpost Project URL.

## Abuse bounds

- Max 5 demo PRs in flight; older than 45 min are auto-closed and their
  branches deleted (`create-demo.js`).
- Max `DEMO_MAX_RUNS_PER_DAY` (40) runs per rolling 24h. GitHub is the
  durable store — every run leaves a `demo/run-*` branch on a PR, so a
  stateless function still enforces a real quota with no database. This is
  the bound that matters when the gate is off, since the access code is
  published to judges and is a courtesy gate, not a bearer secret.
- Both caps return 429 with a `fallback` URL, and the page renders it as a
  link to the judge workbench — a capped-out visitor gets the verified
  reports instead of a dead end.
- The PAT can touch nothing but the demo repo.
- This backend makes no LLM calls itself, but the PR it opens triggers the
  guardian Action, which does spend one model call per run. That is what the
  daily cap is protecting.

The original Python client + mock server + tests in `../` are the tested
reference this backend ports (same API calls, same cleanup semantics).
