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
3. Environment variables: `GITHUB_TOKEN` = the PAT
   (`GH_OWNER`/`GH_REPO` default to `jwlai-cloud`/`fiction-retail-dbt`).
4. Deploy. The URL becomes the Devpost Project URL.

## Abuse bounds

- Max 5 demo PRs in flight; older than 45 min are auto-closed and their
  branches deleted (`create-demo.js`).
- The PAT can touch nothing but the demo repo.
- No LLM calls in this backend — nothing to spend.

The original Python client + mock server + tests in `../` are the tested
reference this backend ports (same API calls, same cleanup semantics).
