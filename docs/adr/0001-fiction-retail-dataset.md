# ADR-0001: fiction-retail as the demo dataset

Status: Accepted (2026-07-15) · supersedes CLAUDE.md's earlier nyc-taxi default

## Context

CLAUDE.md defaulted to nyc-taxi because it "ships with a planted freshness
scenario." Our demo detects schema/logic/semantic changes — freshness never
enters the story; the planted scenario is noise, not an asset. nyc-taxi is
also one flat trips table, which makes a thin lineage graph.

## Decision

fiction-retail. Relational customers/orders structure produces a real
bronze→silver→gold lineage (`stg_customers`/`stg_orders` → `fct_orders` →
`revenue_daily`) and believable cross-team consumers (finance dashboard,
marketing LTV). The staged breaking changes read like real incidents:
column rename on an order fact, a silently-redefined revenue metric, a
drifted "Gross Revenue" definition. Seeds are generated deterministically
(`scripts/generate_seed_data.py`) so the project is self-contained.

## Consequences

Data volume is small (60 customers / 300 orders) — fine, since blast radius
comes from metadata, not row counts. The richer-scale showcase-ecommerce
dataset remains available as backdrop if the DataHub instance needs to look
less empty.
