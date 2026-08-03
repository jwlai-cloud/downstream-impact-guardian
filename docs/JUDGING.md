# For judges — how to evaluate this in 5, 15, or 45 minutes

Four independent routes, cheapest first. Routes 1 and 2 need **no credentials
and no setup**. Routes 3 and 4 use **read-only credentials** — a UI login for
route 3, an API token for route 4 — both in the **Devpost submission's private
testing-notes field** (deliberately not committed to this public repo).

| # | Route | Time | Needs |
|---|---|---|---|
| 1 | [Judge workbench](https://jwlai-cloud.github.io/downstream-impact-guardian/) — four verified runs, checked in | 5 min | nothing |
| 2 | [Live demo button](https://downstream-impact-guardian.vercel.app/) — opens a real PR, agent reports inline | 5 min | nothing |
| 3 | Live DataHub UI — browse the catalog the agent reads | 15 min | read-only UI login (Devpost notes) |
| 4 | Bring your own agent — point an MCP client at the same catalog | 45 min | read-only API token (Devpost notes) |

---

## Route 1 — the workbench (zero credentials)

<https://jwlai-cloud.github.io/downstream-impact-guardian/>

Four tabs, each a **real PR comment** the published Action posted, snapshotted:

| Scenario | Verdict |
|---|---|
| Rename + metric drift + glossary rewrite | 🔴 CRITICAL (24) |
| Whole model deleted | 🔴 CRITICAL (11) |
| One `WHERE` clause tightened | 🟠 HIGH (7) — *suspected* semantic drift |
| Pure expression tweak | 🟠 HIGH (7) with a 🟢 SAFE row — the precision-ladder payoff |

Each links to the live comment on the consumer repo so you can confirm nothing
was hand-edited.

## Route 2 — trigger it yourself

<https://downstream-impact-guardian.vercel.app/>

Pick a scenario, press the button. It opens a **real pull request** against
[an independent dbt repo](https://github.com/jwlai-cloud/fiction-retail-dbt)
that consumes this action via a single `uses:` block. The real GitHub Action
runs and the agent's report renders **on the same page** — severity, blast
radius with owners, the breaking queries, and the generated compatibility code.
Takes ~3–4 minutes end to end. Demo PRs auto-close.

## Route 3 — the live catalog (judge login in Devpost notes)

A self-hosted OSS DataHub instance, populated with the demo's reality. URL and
read-only credentials are in the Devpost testing notes. Worth looking at:

- **Lineage** on `fct_orders` — the cross-system graph: two Looker dashboards
  and three BigQuery datasets across three teams. This is the blast radius no
  single repo can see.
- **Properties** on `marketing.customer_ltv` — the `depends_on_columns`
  declaration, ingested from that consumer's own dbt `meta`. This is what
  turns a worst-case guess into a **fact** (and enables the 🟢 SAFE verdict).
- **Quality → Data Contract** on `fct_orders` — a contract the agent
  **wrote back** as PROPOSED. Merging the PR is the human approval.
- **Glossary → Gross Revenue** — the live business definition the semantic
  detector compares the PR against.

The judge account has the **Reader** role: browsing works, writes are denied.

## Route 4 — interrogate it with your own agent

The repo ships a preconfigured [`.mcp.json`](../.mcp.json) for
`mcp-server-datahub`. Point Claude Desktop / Cursor / any MCP client at the
instance (URL + read-only token in the Devpost notes) and ask it directly:

> *"Who breaks if `fct_orders.order_total` is renamed?"*

You should get the same six consumers the agent found — which is the whole
thesis: the judgment comes from the catalog, not the code.

---

## Criterion → evidence map

| Judging criterion | Where to see it |
|---|---|
| **Agents that do real work** (Track 1) | Route 2 — a real PR, a real Action run, two writebacks: a PROPOSED Data Contract in DataHub (Route 3) and a PR comment with mergeable code |
| **Metadata-aware code generation** (Track 2) | The compat view + `schema.yml` tests in any report — generated from the *live* schema, mergeable as-is |
| **Use of DataHub** | Lineage + observed queries + glossary + contract writeback, via the first-party [Agent Context Kit](https://docs.datahub.com/docs/dev-guides/agent-context/agent-context) and MCP server |
| **Technical execution** | 48 unit tests over the deterministic core; three independent detectors (dbt manifest diff, `sqlglot` expression diff, glossary comparison); [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |
| **Real-world usefulness** | Distributed as a reusable composite Action — one `uses:` block, the consumer's own runner is the compute, no hosting |
| **Honesty / trustworthiness** | The LLM narrates but never scores and never authors merged code; impact is a labeled worst-case bound unless declared; a configured-but-unreachable catalog **fails the run** rather than silently faking it |

## What is deliberately mocked (stated plainly)

The dbt project and its consumers are **fictional** (`fiction-retail`), built
for this demo — our own dbt-shaped project, not the DataHub `static-assets`
SQLite sample, because manifest-diff detection requires dbt artifacts. The
cross-team consumers, dashboards, owner emails, and observed queries were
**seeded** into DataHub to represent a realistic multi-team estate
([`scripts/seed_demo_consumers.py`](../scripts/seed_demo_consumers.py)).

Everything the agent *does* with that reality is real: real Action runs, real
GraphQL reads, a real LLM narrative, real contract upserts, real PR comments.

## Deeper reading

- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — current-state system description
- [`docs/submission-media/DIAGRAMS.md`](submission-media/DIAGRAMS.md) — architecture, agent topology, sequence
- [`docs/LEARNING.md`](LEARNING.md) — what each library does and why
- [`docs/adr/`](adr/) — the decisions, including the rejected alternatives
- [`docs/blog/2026-07-23-designing-honest-blast-radius.md`](blog/2026-07-23-designing-honest-blast-radius.md) — the design story
