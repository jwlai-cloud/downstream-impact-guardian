# CONTEXT.md — ubiquitous language

Glossary only. Implementation lives in code; rationale lives in docs/adr/.
Challenge any use of these words that doesn't match the definition here.

## Terms

**Breaking change** — a schema-shape change to a model that stops downstream
SQL from compiling or returning the old shape: a column removed, renamed, or
type-changed. Strictly structural. A change that alters *values* but not
shape is never "breaking" — that's metric drift. *(Decided 2026-07-15 grill:
schema-strict.)*

**Metric drift** — a logic-only change to a model: consumers' queries still
run, but the numbers they return now mean something different (e.g. gross
revenue silently excluding refunds). A distinct failure mode from a breaking
change: dashboards render, wrongly.

**Semantic drift** — divergence between a business term's definition as
proposed in a PR and the definition currently live in DataHub's glossary.
Detected at the definition level, not the SQL level.

**Suspected semantic drift** — a metric drift on a model whose column is
bound to a glossary term, with no matching glossary update in the PR (the
"forgot the glossary" case). The guardian flags it for verification against
the live definition; it asserts suspicion, never divergence. *(Decided
2026-07-15 grill: heuristic flag, deterministic, no LLM verdict.)*

**Blast radius** — the set of real, cross-system downstream consumers and
observed queries that a change would affect, as evidenced by DataHub lineage
and query history. Never inferred from the repo alone.

**Consumer** — any downstream entity DataHub lineage reaches from a changed
model: another table, a dashboard, a chart — including ones owned by other
teams and living outside this repo.

**Compat view** — generated `<model>_compat` dbt view re-exposing a model's
pre-change schema shape after a breaking change, so consumers keep working
while they migrate.

**Legacy view** — generated `<model>_legacy` dbt view preserving a model's
pre-change SQL logic after metric drift, for consumers pinned to the old
metric definition.

**Data Contract (PROPOSED)** — the durable DataHub record the guardian
writes for an impacted model, bundling that dataset's existing assertions,
stamped as proposed-not-approved. Human approval = merging the PR.

**Reality vs hypothesis** — DataHub only ever reflects reality (what is
live); a PR is read locally as the hypothesis (what is proposed). Nothing
hypothetical is ever ingested into DataHub.

**Offline mode** — first-class agent mode when DataHub/Gemini credentials
are absent: committed fixtures stand in for DataHub, the full report still
renders. Not a test double.

**Severity** — the deterministic LOW/MEDIUM/HIGH/CRITICAL rating computed
from breaking changes, metric drift, semantic drift, consumers, and
query hits. Scored by code, never by the LLM. PR-level: one rating per
check run. ("Impact level" is NOT a synonym — see below.)

**Impact level** — per-consumer classification of what a change does to
one downstream entity: **BROKEN** (it will error — upstream of it a
column was removed/renamed or a model deleted), **DISTORTED** (it keeps
running but its numbers silently change — downstream of metric drift),
**ADVISORY** (only the business meaning shifted — semantic drift).
Worst applicable level wins per consumer, and the level is an honest
**upper bound** derived from the upstream change kind — a consumer that
doesn't touch the changed columns is safe; column-level lineage refines
this per consumer when adopted. *(Decided 2026-07-22 grill: orthogonal
to Severity — Severity says how bad the PR is, impact level says what
can happen to each victim.)*

**Stakeholder** — the DataHub owners of an impacted consumer entity,
resolved from the ownership aspect. An impacted consumer with no owners
is reported as **unowned** — itself a governance finding, never silently
skipped.

**Informing protocol** — how stakeholders learn about impact: the PR
comment always carries the consumer × impact level × owners table; on
HIGH/CRITICAL severity a Slack notification fires when a webhook is
configured; on CRITICAL under strict mode the check blocks until the
compatibility code path is adopted. The Data Contract remains the durable
record for stakeholders who arrive later.
