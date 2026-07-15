# SPEC — design log and rationale

This is the detailed "why," not just the "what" (that's CLAUDE.md). Read this
when you need to understand *why* a decision was made, or before proposing
something that sounds like an improvement — it might already be a dead end
documented below.

## 1. Track and idea selection

Considered 20 ideas across all four hackathon tracks (Agents That Do Real
Work / Metadata-Aware Code Generation / Production ML Agents / Open
Wildcard) before landing here. Filtered for: medium effort, high originality,
high DataHub depth. This idea combines Track 1 and Track 2 legitimately —
it both *takes action based on understanding what's connected* (Track 1's
own language) and *generates code that lands in a PR* (Track 2's own
language) — without needing extra scope to claim both; it's an honest
description of one agent.

**Rejected ideas worth remembering why:**
- Pure NL-to-SQL / text-to-SQL agent — Analytics Agent (DataHub's own
  shipped OSS product) already does this, including charting, follow-ups,
  context quality scoring, and `/improve-context` writeback. Building this
  straight would score low on Originality.
- Standalone "code generation from schema" framing — indistinguishable from
  what Claude Code or Codex already do well. The edge isn't in writing the
  code, it's in knowing what to generate using cross-system context no
  single repo has. This reframing is why the current design leads with
  detection + blast-radius, and treats code generation as the last, small
  step.

## 2. What DataHub already ships (don't rebuild)

Audited before building anything:

| Component | What it is |
|---|---|
| MCP Server | Read tools (search, get_lineage, get_dataset_queries, get_glossary_term_versions, compare_glossary_term_versions, list_pending_proposals) + mutation tools (add_tags, add_owners, update_description, set_lifecycle_stage, save_document, glossary term CRUD, propose_*/accept_or_reject_proposals) |
| Agent Context Kit | Python SDK wrapping the same tools for LangChain/ADK, with three explicit reference patterns in the docs: Text-to-SQL agent, Data Quality agent, Data Steward/Governance agent |
| DataHub Skills | 5 Claude Code/Cursor/Copilot/Gemini-CLI skills: search, lineage, enrich, quality, setup |
| Analytics Agent | Full running Apache 2.0 app: NL→SQL→chart, context quality score, `/improve-context` writeback |

The judging rubric explicitly rewards going beyond these ("Submissions
should clearly go beyond features DataHub already provides out of the box").
This is why the design deliberately uses MCP/Agent Context Kit as plumbing
and puts all the actual novelty in the three-source detection + blast-radius
+ dual-writeback loop, none of which any shipped DataHub product does.

## 3. Agent framework: why ADK, not Strands, not Antigravity

- **Google ADK**: DataHub has a first-party, documented integration
  (`pip install datahub-agent-context[google-adk]`), with working example
  scripts (`basic_agent.py`, `simple_search.py`) and support for both
  embedded Python tools and `McpToolset`. Matches the user's existing
  GCP/BigQuery/Airflow stack — Application Default Credentials just work.
- **AWS Strands**: checked — no DataHub integration guide exists at all.
  Would require wiring the DataHub MCP endpoint into Strands manually with
  zero reference implementation to debug against. Rejected: pure plumbing
  risk for zero benefit, and introduces a second cloud for no reason.
- **Gemini Antigravity managed agent** (`ai.google.dev/gemini-api/docs/
  custom-agents` / `antigravity-agent`): checked directly against Google's
  own docs. The Limitations section explicitly states `mcp` and
  `function_calling` are "not yet supported." This closes off BOTH of
  DataHub's integration paths (MCP Server needs `mcp`; Agent Context Kit's
  raw Python tools need `function_calling`). Not a documentation gap — a
  real, current product limitation. Rejected outright, not a matter of
  extra effort.
- **LangChain/LangGraph**: also officially documented by DataHub, and the
  user has production experience with LangGraph from a prior multi-agent
  project (RehabPanel). Equally valid fallback to ADK if ADK friction
  appears; not a downgrade.

## 4. Why three separate detection sources, not one

Initially assumed DataHub's schema history alone would cover "what changed."
On further questioning (the user's real pain: schema change, upstream logic
change, semantic/business-definition change, and lack of proper data
contracts), checked whether DataHub tracks logic changes too.

**Finding:** DataHub's Timeline API covers ownership, tags, technical
schema, documentation, and glossary-term assignment history for Datasets,
Glossary Terms, Domains, and Data Products — event-sourced, every aspect
version retained. It does NOT have a confirmed native mechanism for diffing
a dbt model's compiled SQL/business logic across ingestion runs. Rather than
assume this works, or build something fragile expecting it to, the design
uses `dbt build --select state:modified+` for logic-change detection —
dbt's own, already-trusted mechanism for exactly this purpose (used in dbt's
own CI tooling for detecting "breaking change to an enforced contract").

This is a case where honesty about a tool's limits produced a *better*
architecture: each source does only what it's actually good at. dbt sees its
own DAG and logic; DataHub sees cross-system usage that dbt cannot.

## 5. Data Contracts — corrected mid-design, worth remembering

First pass incorrectly concluded Data Contracts required DataHub Cloud and
had no public creation API, based on one doc page's "API guide... coming
soon" language (`docs/managed-datahub/observe/data-contract`). A second,
more specific tutorial page (`docs/api/tutorials/data-contracts`) documents
a fully working `upsertDataContract` GraphQL mutation, and a governed
`proposeDataContract` mutation exists alongside DataHub's other propose/
approve mutations. DataHub's own docs are inconsistent across pages here —
worth filing as feedback during the hackathon's Feedback Period (counts
toward nothing directly, but is good community citizenship and the kind of
thing that could be mentioned).

**Caveats that survived the correction, still true:**
- A Data Contract bundles existing assertions — it can't be created with
  no assertions behind it. Solved via dbt tests → DataHub assertions
  (confirmed self-hosted-compatible via the dbt ingestion source, which
  translates `run_results` into `AssertionResult`s automatically).
- DataHub's own docs caution that GraphQL mutations are "primarily designed
  for UI interactions... should generally be avoided in programmatic,
  high-throughput use cases; use the Python SDK instead." For our use case
  (one contract per detected incident, not bulk), this is an acceptable,
  low-volume exception — worth one honest line in the submission writeup
  rather than pretending the caveat doesn't exist.

## 6. Writeback design — two, not one

Early framing treated "post a PR comment" as the entire writeback. On
reflection, this only helps humans on that specific PR, right now — it
doesn't help the next engineer or agent who looks the table up in DataHub
months later. The track's own language — "writes results back so the next
person or agent inherits the knowledge" — points at DataHub as a durable,
catalog-level record, not git history. Hence two separate writebacks (see
CLAUDE.md), with the DataHub one created first so the PR comment can
reference something durable rather than describing a one-off finding.

## 7. Interface: PR bot, not chatbot

Early brainstorming assumed a conversational agent (ask questions, get
answers). The user's actual stated pain — teams changing things without
proper data contracts, unexpected consequences to production pipelines —
pointed at something proactive and embedded in the existing workflow,
not something someone has to remember to query. Hence: GitHub Action on
`pull_request`, not a chat UI as the primary interface.

## 8. The triggerable web UI — built ahead of schedule, deliberately deferred

A stretch-goal web UI (button → creates a real branch+PR with a timestamped
name → real GitHub Action fires → live progress narration → judge sees the
actual PR comment land) was fully designed, built, and tested against a
mock GitHub API server (see `tools/demo_ui/`) — including catching two real
bugs (a timeout path that silently reported false success, and an
under-strict mock auth check). This code is ready to wire into a real
GitHub token whenever there's time left after the core loop is solid, but it
is explicitly NOT required for a working submission — the pre-made `demo/*`
branch approach satisfies the judge-testing requirement without it. Do not
let this compete for time against the core loop.

## 9. Cost and hosting

- Public datasets from the hackathon's own Resources page (all Apache
  2.0-clear): showcase-ecommerce (1,049 entities, instant scale/backdrop),
  bootstrap (lightweight starter), nyc-taxi (~500k trips, planted freshness
  issue), healthcare (~55k records, planted DQ issues), fiction-retail
  (50k customers/150k orders, clean canvas).
- BigQuery sandbox + dbt Core + local Docker Airflow (if ever needed) are
  all free at these dataset sizes.
- DataHub hosting is the one real cost lever: self-hosted GCE VM for the
  ~3-week judging window (~$30-60) vs. DataHub Cloud free trial (watch
  expiry timing against Aug 17-31) vs. leaning on video+repo as primary
  judged evidence (rules explicitly permit this).
- Realistic ceiling: under $75 total even hosting everything through
  judging.

## 10. Explicit non-goals for this build

- Not building a novel agent orchestration engine — the harness is supposed
  to be boring (see judging criteria: "Use of DataHub" is listed first and
  weighted equally with Technical Execution; harness sophistication is not
  a judged criterion at all).
- Not running live Airflow unless a specific idea component demands
  orchestration semantics (this design doesn't).
- Not ingesting hypothetical/PR-branch state into the judge-facing DataHub
  instance — DataHub only ever reflects reality.

## 11. Grill session 2026-07-15 — open questions resolved, one correction

All five open questions from CLAUDE.md were decided with the user in one
session. Decisions and full rationale live in `docs/adr/0001`–`0008`;
CLAUDE.md carries the summaries. Two findings from the session worth
recording here because they correct or sharpen earlier sections:

**Correction to section 5 (Data Contracts).** Verified against
`docs/api/tutorials/data-contracts` on 2026-07-15: the tutorial documents
`upsertDataContract` ONLY and states it "specifically covers how to use the
Data Contract APIs with DataHub Cloud." `proposeDataContract` does not
appear on that page at all; the proposal/inbox workflow is a DataHub Cloud
feature. Section 5's claim that a governed `proposeDataContract` mutation
was available to us was over-optimistic. Since we chose self-hosted OSS
(ADR-0003), the writeback design is now: try `upsertDataContract` against
the OSS GraphQL schema; if absent, emit `dataContractProperties` directly
via the Python SDK. Either way the contract is marked PROPOSED (via
status/customProperties) and the human approval gate is the PR merge
itself. This stays honest to the original intent (a human approves new
contracts) without depending on a Cloud-only mutation.

**Judge-path secrets hole, and the fix.** Fork PRs receive no repository
secrets, so an agent triggered from a forked PR can reach neither DataHub
nor Gemini. Two-part fix: (a) the documented judge path is opening a PR
from the pre-made `demo/*` branch to `master` *within this repo* — public
repos allow anyone with read access to open a PR between existing branches,
no fork required — which runs with real secrets; (b) the agent has a
first-class offline fixture mode (ADR-0007) that produces the complete
comment from committed fixtures when secrets are absent, and always writes
the comment body to `$GITHUB_STEP_SUMMARY` so output is visible even when
comment posting is impossible. The offline mode also let the whole agent be
built and tested before any live DataHub instance existed.
