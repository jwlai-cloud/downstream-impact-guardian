# Project context for Claude Code

This file is read automatically. It captures everything already decided so
work doesn't restart from zero each session. Treat these as settled unless
the user explicitly reopens them.

## What we're building

A Downstream Impact Guardian for the "Build with DataHub: The Agent Hackathon"
(deadline Aug 10, 2026 registration/submission; judging Aug 17–31 2026;
$20,500 prize pool). Full rules: https://datahub.devpost.com/rules

**One-line pitch:** an agent that detects breaking schema/logic/semantic
changes via DataHub before they ship, assesses real cross-system blast
radius via lineage, proposes a Data Contract back into DataHub, and posts a
PR comment with generated compatibility code.

**Primary track:** Agents That Do Real Work (reads DataHub to understand
what's connected to what, takes action, writes results back). Has a
legitimate secondary claim on Metadata-Aware Code Generation & Development
(generates real, PR-mergeable code) — mention both in the submission
description, pick Track 1 as primary if the form forces one choice.

## Decisions already made — don't relitigate without new information

- **Don't rebuild what DataHub already ships.** MCP Server, Agent Context
  Kit, DataHub Skills, and Analytics Agent already cover: search, lineage,
  text-to-SQL, data quality monitoring, and metadata enrichment at scale.
  Our differentiator is NOT reading metadata — it's the cross-referenced
  judgment call (schema/logic/semantic change + real lineage blast radius)
  and the two writebacks. See docs/SPEC.md for the full "what's already
  shipped" audit.
- **Agent framework: Google ADK.** Core loop runs the agent *inside the
  GitHub Action runner* (`python agent/main.py`) — Cloud Run hosting is only
  relevant to the stretch-goal web UI, not the core loop (ADR-0008). DataHub ships
  a first-party, documented ADK integration (`datahub-agent-context[google-adk]`)
  with working examples. LangChain is an equally safe fallback (also
  officially documented by DataHub) if ADK friction shows up — the user has
  production LangGraph experience from a prior project. Do NOT use AWS
  Strands (no DataHub integration exists) or Gemini's Antigravity managed
  agent (explicitly does not support `mcp` or `function_calling` as of the
  docs checked — see docs/SPEC.md).
- **Change detection is three separate sources, not one:**
  - Schema changes → DataHub schema history / Timeline API
  - Business logic changes → `dbt build --select state:modified+` (compares
    manifest.json against last known production state) — NOT a DataHub-native
    mechanism, dbt already solves this correctly
  - Semantic/glossary definition changes → DataHub
    `compare_glossary_term_versions`
- **Blast radius is DataHub's job specifically** — `get_lineage` +
  `get_dataset_queries`, because this is the one thing no single repo or
  coding agent can see (cross-system, cross-team usage).
- **Two separate writebacks, both required, in this order:**
  1. To DataHub: a Data Contract, durable catalog-level record. VERIFIED
     2026-07-15: `proposeDataContract`/proposal-inbox is DataHub Cloud-only
     and the Data Contracts API tutorial is explicitly Cloud-scoped. On
     self-hosted OSS (our chosen hosting, see ADR-0003) the writeback is
     `upsertDataContract` if present in the OSS GraphQL schema, else direct
     SDK emission of `dataContractProperties`, with the contract marked
     PROPOSED via status/customProperties — human approval = PR merge.
  2. To the repo: PR comment + generated compatibility SQL view + tests,
     referencing the DataHub contract created in step 1.
- **Trigger: GitHub Actions on `pull_request` (opened/synchronize).** This is
  the real, primary interface — not a chatbot, not a UI-first experience.
- **DataHub only ever reflects reality.** Never `datahub ingest` a PR
  branch's hypothetical state — that pollutes the graph with metadata for
  changes that might get rejected. The agent reads DataHub for "what's
  really live," and reads the PR/dbt diff locally for "what's proposed."
- **Data prep is a one-time step, not a live dependency.** Pick ONE public
  dataset (nyc-taxi is the default choice — ships with a planted freshness
  scenario already; fiction-retail is the fallback if a clean canvas is
  preferred), load into BigQuery sandbox (free tier), build a small dbt
  project (3-4 models, bronze/silver/gold), deliberately introduce one
  schema change and one logic change across two ingestion runs so DataHub's
  history isn't empty, `datahub ingest` it in. No live Airflow needed unless
  a specific idea requires orchestration semantics (this one doesn't).
- **Judge-facing test path: a pre-made `demo/*` branch in this repo.** Judge
  forks, opens a PR from that branch, watches the real Action fire. This
  satisfies the rules' "provide easy access for judges to test" requirement
  without needing a second interface.
- **The triggerable web UI (button that opens a real PR on demand, with live
  progress narration) is a STRETCH GOAL ONLY.** Core loop must be fully
  solid first. Working, tested code for this already exists in
  `tools/demo_ui/` (GitHub API client + mock server + tests) — it's ahead of
  where the core loop currently is, intentionally, so it's ready to wire up
  if time remains, but do not let it compete for time against the core loop.
- **Cost ceiling: under $75 total** for the full judging window, dominated
  by whether DataHub is self-hosted 24/7 vs. DataHub Cloud free trial vs.
  relying on video+repo as primary evidence (rules explicitly permit the
  latter — judges aren't required to test live).

## Formerly-open questions — RESOLVED in grill session 2026-07-15

All five decided with the user; full rationale in docs/adr/. Don't reopen
without new information.

- **Dataset: fiction-retail** (ADR-0001). Clean canvas + relational
  customers/orders structure gives a real bronze/silver/gold lineage story
  and believable cross-team consumers. nyc-taxi's planted freshness scenario
  is irrelevant to a schema/logic/semantic-change demo.
- **Compatibility artifact: one dbt compat view + schema.yml tests**
  (ADR-0002). No macro. Mergeable as-is, appears in DataHub lineage on next
  ingest.
- **Hosting: self-hosted OSS DataHub** — Docker quickstart for dev, GCE VM
  for the judging window (ADR-0003). Removes Cloud-trial expiry risk over
  Aug 17–31. Consequence (verified): no proposal inbox; contract writeback
  is upsert/SDK-emission with PROPOSED status.
- **GitHub auth: built-in Actions `GITHUB_TOKEN`** with
  `pull-requests: write` (ADR-0004). PAT-vs-App only matters for the stretch
  UI; decide there if/when it's built.
- **Semantic layer: formal glossary terms** via `business_glossary.yml`
  ingestion, attached through dbt `meta` (ADR-0005). Uses
  `compare_glossary_term_versions` as designed.

Additional decisions from the same session:
- **Prod dbt manifest is committed to the repo** at
  `dbt_demo_project/prod_state/manifest.json` (ADR-0006) — the only
  zero-infra way the state comparison works for judge-opened PRs.
- **Offline fixture mode is a first-class agent mode** (ADR-0007): if
  DataHub/Gemini secrets are absent (fork PRs get no secrets), the agent
  runs against committed fixtures and still renders the full comment +
  writes it to `$GITHUB_STEP_SUMMARY`. Judge path avoids the problem
  entirely: a PR from the pre-made `demo/*` branch *within this repo* (no
  fork needed — read access suffices to open a PR between existing branches
  of a public repo) runs with real secrets.
- **Detection uses `dbt ls`/manifest diff, not `dbt build`** — `build`
  executes against the warehouse, which CI neither needs nor can do without
  creds. dbt's state:modified mechanism is kept; the execution isn't.

## Distribution shape (decided 2026-07-15, session 2)

- **The agent is a reusable composite GitHub Action** (`action.yml` at repo
  root) — any dbt repo adopts it with one `uses:` block; this repo dogfoods
  its own action. No hosted agent, ever: the consumer's Action runner is
  the compute (ADR-0008). Feeds the "Real-World Usefulness" judging
  criterion directly.
- **Live reads for the ADK narrative agent go through the DataHub Agent
  Context Kit** (`datahub-agent-context[google-adk]`,
  `build_google_adk_tools`, mutations off) — Track 1's named integration
  path. Deterministic pipeline keeps direct GraphQL where the Kit has no
  equivalent: contract upsert, sibling-aware assertion lookup.

## Domain language

`CONTEXT.md` at the repo root is the glossary (ubiquitous language):
breaking change (schema-strict), metric drift, semantic drift, suspected
semantic drift, blast radius, compat/legacy views, PROPOSED contracts,
reality-vs-hypothesis, offline mode. Challenge any usage that conflicts
with it; update it the moment a term is resolved. Contract scope is one
per impacted model (ADR-0009); the check is advisory by default
(`--strict` is the opt-in gate).

## Key external references

- Hackathon rules: https://datahub.devpost.com/rules
- Hackathon resources (sample datasets, docs links): https://datahub.devpost.com/resources
- DataHub MCP Server: https://docs.datahub.com/docs/features/feature-guides/mcp
- DataHub Agent Context Kit: https://docs.datahub.com/docs/dev-guides/agent-context/agent-context
- DataHub Google ADK guide: https://docs.datahub.com/docs/dev-guides/agent-context/google-adk
- DataHub Skills: https://docs.datahub.com/docs/dev-guides/agent-context/skills
- DataHub Timeline API: https://docs.datahub.com/docs/dev-guides/timeline
- DataHub Data Contracts API tutorial (`upsertDataContract`,
  `proposeDataContract`): https://docs.datahub.com/docs/api/tutorials/data-contracts
- dbt state comparison: https://docs.getdbt.com/reference/node-selection/methods#state

## How to work with the user in this repo

- Direct, technically fluent, prefers concise actionable output over long
  preamble.
- Artifact-first: prefers seeing real code/files over descriptions of code.
- Iterative slice-by-slice development with diff review.
- Pushes back when responses are too cautious or under-specified — match
  that energy; don't hedge unnecessarily, but flag real uncertainty honestly
  rather than asserting things that haven't been verified (see docs/SPEC.md
  for examples of claims that were checked and corrected mid-design, e.g.
  Data Contracts API availability).
- Full context of how this design was arrived at, including dead ends
  (Strands, Antigravity, standalone code-gen framing) is in docs/SPEC.md —
  read it before proposing alternatives that were already considered and
  rejected, to avoid re-litigating settled decisions without new information.
