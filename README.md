# Downstream Impact Guardian

**Build with DataHub: The Agent Hackathon** — submission in progress.

An agent that catches breaking changes — schema, business logic, and semantic
definitions — *before* they land, by reading DataHub's context graph and
generating a real, mergeable fix.

## The problem

When teams change a dbt model's schema, its SQL logic, or a business glossary
definition, downstream consumers — other teams' pipelines, dashboards, ML
features — often find out only when something breaks in production. Without
proper data contracts, this is exactly the kind of silent, cross-team failure
that no single repo's CI can catch on its own, because no single repo knows
who else depends on it.

## What this agent does

Triggered on every pull request to a dbt project:

1. **Detects** what actually changed — schema and logic (prod-vs-PR dbt
   manifest diff, dbt's own `state:modified` semantics), and semantic
   definitions (the PR's glossary vs the live DataHub glossary)
2. **Assesses blast radius** — cross-references DataHub lineage and query
   history to find every real downstream consumer, across systems, not just
   within this one repo
3. **Writes back to DataHub** — proposes a Data Contract formalizing the
   dependency that was just discovered, so the next person or agent inherits
   the knowledge
4. **Writes back to the repo** — posts a PR comment with generated,
   backward-compatible dbt views (`*_compat` / `*_legacy`) plus tests, so a
   data team could actually merge it

## Why this needs DataHub, not just a coding agent

Any coding agent can write a compatibility view once told what changed. Only
a context platform like DataHub knows the change happened at all, in the
first place, and who else in the organization is quietly depending on the old
shape. The value here is in *knowing what to generate*, not the generation
itself.

## Use it in your own dbt repo

The guardian is a reusable composite GitHub Action — no hosting, it runs on
your repo's Action runner on every PR:

```yaml
on:
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  pull-requests: write

jobs:
  guardian:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: jwlai-cloud/downstream-impact-guardian@master
        with:
          dbt-project-dir: transforms          # your dbt project path
          datahub-url: ${{ secrets.DATAHUB_GMS_URL }}
          datahub-token: ${{ secrets.DATAHUB_GMS_TOKEN }}
          google-api-key: ${{ secrets.GOOGLE_API_KEY }}   # optional narrative
          warehouse-project: my-gcp-project
          warehouse-dataset: analytics
```

Requirements in your repo: a parse-able `profiles.yml` in the dbt project
dir, a committed last-known-production manifest at
`<dbt-project-dir>/prod_state/manifest.json`, and (optionally) a
`datahub/business_glossary.yml` for semantic-drift detection. All inputs in
[`action.yml`](action.yml). This repo consumes its own action — the demo
workflow is the reference integration.

## Try it (judges)

Open a PR from the pre-made [`demo/breaking-change`](../../compare/master...demo/breaking-change)
branch to `master` **in this repo** — no fork needed. The branch stages one
schema break (`order_total` → `order_amount_usd`), one silent metric
redefinition (gross revenue quietly drops refunds), and one glossary drift.
The Action fires, and the guardian posts its full report as a PR comment.
Can't open a PR? The exact same generated output is committed in
[`examples/generated/`](examples/generated/).

**Second test path — bring your own agent.** The demo catalog speaks
[DataHub MCP](https://docs.datahub.com/docs/features/feature-guides/mcp):
point Claude Code / Claude Desktop / Cursor at it and interrogate the
lineage, glossary, and the guardian's PROPOSED Data Contract yourself:

```jsonc
// .mcp.json (this repo ships one preconfigured for local quickstart)
{ "mcpServers": { "datahub": {
    "command": "uvx", "args": ["mcp-server-datahub"],
    "env": { "DATAHUB_GMS_URL": "http://<demo-instance>:8080",
             "DATAHUB_GMS_TOKEN": "<token from submission notes>" } } } }
```

Ask it "who breaks if fct_orders drops order_total?" — same context graph
the guardian reads in CI.

## Status

Core loop complete, tested (26 tests, no network needed), and proven live in CI:
detection (dbt manifest diff + glossary drift) → blast radius (DataHub
lineage + observed queries) → Data Contract writeback (PROPOSED) →
deterministic compat codegen → idempotent PR comment. See
`docs/ARCHITECTURE.md` for the system shape, `docs/adr/` for decisions,
`docs/SPEC.md` for design history, `docs/PROGRESS.md` for current state,
and `CLAUDE.md` for working context. The live path (lineage, glossary
drift, `upsertDataContract`) is verified against a real self-hosted OSS
instance; the standing demo PR (#1) carries a real guardian report posted
by the Action. Remaining before submission: judge-facing instance
(`docs/ORACLE_BRINGUP.md`), repo secrets, demo video.

## License

Apache 2.0 — see [LICENSE](./LICENSE).
