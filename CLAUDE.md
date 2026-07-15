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
- **Agent framework: Google ADK on GCP, hosted on Cloud Run.** DataHub ships
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
  1. To DataHub: `proposeDataContract` (bundling the relevant assertion,
     which can come from ingested dbt test results) — the durable,
     catalog-level record. Governed/proposal form preferred over direct
     `upsertDataContract` since a human should approve a new contract.
  2. To the repo: PR comment + generated compatibility SQL/dbt macro + tests,
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

## Open questions to keep grilling on on in this repo

- Which public dataset, finally: nyc-taxi vs. fiction-retail — pick based on
  whether the "planted freshness issue" story is worth more than a clean
  canvas for staging a logic change deliberately.
- Exact shape of the generated compatibility artifact (SQL view vs. dbt
  macro vs. both) — depends on the specific schema/logic change staged in
  prep.
- DataHub Cloud free trial vs. self-hosted GCE VM for the judge-facing
  instance — trial timing risk vs. hosting cost/maintenance.
- GitHub auth for the Action + agent: fine-grained PAT vs. GitHub App —
  App is more correct for a real product but more setup; PAT is faster for
  a hackathon timeline.
- Whether to formalize glossary terms (richer semantic-layer story, more
  setup) or just use dbt's plain `description:` field (simpler, still
  tracked by DataHub's Timeline API under DOCUMENTATION) for the semantic
  change detection demo.

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
