# ADR-0005: Formal glossary terms for semantic-drift detection

Status: Accepted (2026-07-15)

## Context

Semantic-change detection could use plain dbt `description:` fields
(tracked by the Timeline API under DOCUMENTATION) or formal DataHub
glossary terms (versioned, comparable via
`compare_glossary_term_versions`).

## Decision

Formal glossary terms. `dbt_demo_project/datahub/business_glossary.yml`
defines "Gross Revenue" and "Active Customer"; the datahub-business-glossary
source ingests them (re-ingestion creates new versions); dbt column
`config.meta.business_glossary_term` attaches them to columns via the dbt
source's `column_meta_mapping`.

Detection direction matters: the agent compares the **PR's proposed**
definition (the yml in the diff) against the **live** definition in
DataHub — never the reverse, since DataHub only ever reflects reality.

## Consequences

Small extra prep (one yml, one recipe) buys the named
glossary-version-comparison API from the pitch, a genuinely stronger
semantic-layer story, and a crisp demo moment: the PR redefines Gross
Revenue while the business, per DataHub, still means something else.
