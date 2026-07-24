---
title: "The PR looks fine. Your catalog knows better."
dek: "I built a PR bot that reads DataHub to find out who a dbt change is about to break — then writes back a Data Contract and the compatibility code to fix it."
tags: [datahub, dbt, dataengineering, ai]
canonical_url: https://github.com/jwlai-cloud/downstream-impact-guardian
---

# The PR looks fine. Your catalog knows better.

Here's a PR I've merged, and one you probably have too. Someone tweaks the
logic of a single field in a dbt model — say `gross_revenue` quietly stops
subtracting refunds. Every test passes. CI is green. The PR looks *fine*.
Three weeks later an analyst says "this revenue number looks weird," and
someone spends two days walking the chain backwards: dashboard, mart,
staging, ingestion. I've done that walk. If you work on a data team, you've
done that walk.

The thing that took me too long to accept is that **the repo can't fix
this.** Of course CI was green — nothing *in the repo* broke. The scheduled
query that broke belongs to finance. The LTV table belongs to marketing.
Different repos, different teams, and in any real org — thousands of models,
dashboards everywhere — no one can see everyone else's code. The only place
the whole dependency graph exists is the catalog.

So I built **Downstream Impact Guardian**: a GitHub Action that, on every
dbt PR, reads DataHub for what's actually live, reads the PR for what's
proposed, and posts a comment about who gets hurt.

## The hard half isn't detection

Detecting that a schema changed is the easy half. A diff finds it; CI finds
it. The hard half is knowing *who downstream depends on it*, and that
knowledge lives in the catalog, not the code. That asymmetry is the entire
reason the agent reaches for DataHub instead of staying inside the repo.
Everything below is built around it.

## How it works

**Three detectors, because "breaking change" is really three problems.**

1. **Schema break** — a column removed, renamed, or a whole model deleted.
   Detected by diffing the PR's dbt manifest against a committed
   last-known-production manifest, using dbt's own `state:modified`
   semantics. It runs `dbt parse` (never `dbt build`), so CI needs zero
   warehouse credentials.
2. **Metric drift** — the columns are untouched but the *numbers* silently
   change (refunds quietly dropped). Detected with `sqlglot`, diffing each
   column's SQL expression so the report can name *which* field's logic
   moved. This is the expensive failure: the dashboard still renders,
   wrongly.
3. **Semantic drift** — the *definition* moved. The glossary says gross
   revenue includes refunds; the PR's yml now says it doesn't. Detected
   against DataHub's live glossary, and flagged as *suspected* (never
   asserted) for the very common "changed the logic, forgot the glossary"
   case.

**Then the blast radius — DataHub's job specifically.** The agent walks
lineage (`searchAcrossLineage`, cache skipped so a stale graph can't shrink
the answer), collapses the dbt-and-warehouse sibling nodes into one logical
consumer, and pulls the observed queries that still reference the old shape.
Every impacted consumer comes with its **owners**, straight from the
ownership aspect — an unowned consumer is printed in bold as a governance
finding, not hidden. The blast-radius table reads *consumer × impact × who
to tell.*

**Per-consumer impact is honest about what it can't know.** A dashboard
that only reads `order_id` survives an `order_total` rename, but table-level
lineage can't see that — so the default verdict is a labeled *worst-case*
upper bound. On top of that I built a precision ladder: **declared > derived
> worst-case**. When a consumer declares the columns it reads
(`depends_on_columns` in its own dbt meta, ingested onto its DataHub
entity), the guardian intersects that with the changed columns — a match is
BROKEN *as a fact*, and a non-match earns the one verdict worst-case can
never give: 🟢 **SAFE**. The incentive loop closes itself: declaring your
dependencies is how you stop getting worst-cased.

**Two writebacks.** First, into DataHub: a Data Contract for each impacted
model, `upsertDataContract`'d with PROPOSED status — the catalog now durably
records "this shape was promised," and merging the PR *is* the human
approval. Second, into the repo: one idempotent PR comment carrying the
verdict, the blast-radius table, the breaking queries, and generated,
mergeable compatibility code — `*_compat` / `*_legacy` dbt views plus
schema tests that keep old consumers alive through the change.

## The honesty stance

This is the part I care about most. The scoring, the per-consumer verdicts,
the generated SQL, and the Data Contract are **pure functions of the
detected facts** — deterministic, and covered by 48 unit tests that run with
no network. The LLM never touches any of them.

What the LLM *does* is narrate: it reads the detected facts, cross-checks the
blast radius against DataHub with read-only tools, and writes the impact
story for the PR author. It's a real model call on every configured run —
provider-flexible by repo configuration (`gemini-*` runs on Google ADK's
native path; anything else, like the `openai/qwen3.6-flash` my demo uses on
DashScope, is wrapped in ADK's LiteLLM adapter). It retries transient
provider blips, and on genuine failure it falls back to a template summary
with a prominent warning banner — the facts and tables are unaffected,
because they were never the model's to produce.

Two invariants hold the whole thing up:

- **DataHub only ever reflects reality.** The PR's hypothetical state is
  *never* ingested. A catalog polluted with maybe-merged changes is worse
  than no catalog. A connection that's configured but unreachable fails the
  run — it never silently drops to fixtures and passes them off as live.
- **The LLM narrates; it never scores and never authors merged code.**

## Distribution: no server, ever

The whole thing is a reusable composite GitHub Action. A dbt repo adopts it
with one `uses:` block; the consumer's own runner is the compute, so the
publisher's keys never leave the publisher's repo. Fork PRs (which get no
secrets) fall back to a first-class offline fixture mode, clearly labeled.
This repo dogfoods its own action.

## Try it

- **One-button demo** — pick a scenario, it opens a real breaking PR
  against an independent dbt repo and renders the guardian's report inline:
  <https://downstream-impact-guardian.vercel.app/>
- **Zero-credential judge workbench** — the full story in ~60 seconds:
  <https://jwlai-cloud.github.io/downstream-impact-guardian/>
- **Code** (Apache 2.0):
  <https://github.com/jwlai-cloud/downstream-impact-guardian>
- **How it's built** — an interactive engineering deep-dive:
  <https://claude.ai/code/artifact/c578039e-bce6-4330-8396-cb48b739e7c6>

The PR looks fine. DataHub knows better.
