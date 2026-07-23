<!-- downstream-impact-guardian -->

## 🔴 Downstream Impact Guardian — **CRITICAL** (score 24)

## Impact Narrative

This PR is **CRITICAL** and cannot be merged as-is. Two interlocking breaking changes will cascade through your analytics pipeline:

**Schema break:** Renaming `fct_orders.order_total` → `order_amount_usd` immediately crashes `revenue_daily`, which still references `sum(order_total)` in its SQL. This ripples to every consumer of `revenue_daily`.

**Broken consumers:** At least five assets are already impacted:
- **Finance KPIs** (Looker) — the primary board finance dashboard, owned by finance-bi@fiction-retail.example, will fail.
- **customer_ltv** (BigQuery, marketing-analytics) explicitly depends on `fct_orders.order_total`; its LTV calculations will break entirely.
- **exec_daily_digest** and **Monthly Board Pack** — two more Finance-owned assets at hop 2/3 will also fail.
- **open_orders_snapshot** (ops-eng) will see distorted data due to the logic shift.

**Glossary conflict:** The proposed "Gross Revenue" definition changes the *meaning* of the metric (from all non-cancelled orders to only fulfilled/completed/shipped orders). This semantic shift conflicts with `revenue_daily.gross_revenue`, which semantically encodes "all non-cancelled orders." Aligning this without a coordinated multi-model rewrite will create financial misreporting.

---

## ACTIONS:

1. **Rename the column everywhere first** — update `revenue_daily.sql` to reference `order_amount_usd` instead of `order_total` before merging. Without this, your own model fails to compile.
2. **Align the glossary definition or rename the metric** — either revert the "Gross Revenue" definition change, OR introduce a new model/metric (e.g., `fulfilled_revenue_daily`) so finance doesn't suddenly get a different definition applied to existing dashboards and reports.
3. **Notify downstream teams proactively** — email finance-bi@fiction-retail.example, marketing-analytics@fiction-retail.example, and ops-eng@fiction-retail.example about the required view/dashboard/model updates on their side, particularly for `customer_ltv` and the Finance KPIs dashboard.

_Narrative by `openai/qwen3.6-flash` via Google ADK + DataHub Agent Context Kit._

### What changed

| Model | Change | Details |
|---|---|---|
| `revenue_daily` | logic | logic changed in: `avg_order_value`, `gross_revenue` |
| `fct_orders` | logic + schema | `order_total` → `order_amount_usd`; SQL logic modified (filters/joins/shape) |

### Blast radius & who to inform (from DataHub lineage + ownership — live systems, not this repo)

| Downstream consumer | Platform | Type | Worst-case impact | Stakeholders to inform |
|---|---|---|---|---|
| Finance KPIs | looker | dashboard | 🔴 BROKEN | finance-bi@fiction-retail.example |
| exec_daily_digest | bigquery | dataset | 🔴 BROKEN | finance-ops@fiction-retail.example |
| Monthly Board Pack | looker | dashboard | 🔴 BROKEN | ⚠️ **unowned** — assign an owner in DataHub |
| customer_ltv | bigquery | dataset | 🔴 BROKEN | marketing-analytics@fiction-retail.example |
| open_orders_snapshot | bigquery | dataset | 🟠 DISTORTED | ops-eng@fiction-retail.example |
| revenue_daily | dbt | dataset | 🔴 BROKEN | ⚠️ **unowned** — assign an owner in DataHub |

> Impact is the honest upper bound from the upstream change kind — except 🟢 SAFE rows, which are FACTS: those consumers declared the columns they read (`depends_on_columns` in their own dbt meta) and none were touched. Declare yours to earn the same verdict; column-level lineage will refine the rest.

### Column-level effects (evidence held today)

| Column | What happened | Observed evidence |
|---|---|---|
| `revenue_daily.avg_order_value` | expression changed | — |
| `revenue_daily.gross_revenue` | expression changed | 1 observed query reference it |
| `fct_orders.order_total` | renamed → `order_amount_usd` | 2 observed queries reference it |

> Which downstream consumers read each column needs column-level lineage — roadmap. Everything above is direct evidence, not inference.

### Queries that WILL break

These are real queries DataHub has observed against the old columns:

**on `fct_orders`** (SYSTEM):
```sql
SELECT order_date, SUM(order_total) AS revenue
FROM `agent-era.fiction_retail.fct_orders`
WHERE order_status = 'completed'
GROUP BY order_date
```

**on `fct_orders`** (SYSTEM):
```sql
SELECT customer_id, AVG(order_total) AS aov
FROM `agent-era.fiction_retail.fct_orders`
GROUP BY customer_id
```

### Semantic drift (DataHub glossary)

**Gross Revenue**
- DataHub (current business meaning): Sum of order_total over all non-cancelled orders in the period, refunds included. Refunds are netted out downstream in net revenue, never here.
- This PR proposes: Sum of order_amount_usd over fulfilled (completed or shipped) orders in the period, refunds excluded. revenue, never here.

### Writeback 1 — Data Contracts in DataHub

✅ **`revenue_daily`** — contract `urn:li:dataContract:eaf95bfa-9c31-416b-ba29-f3e1fdf76a24` written (upserted), status **PROPOSED** — approving it = merging this PR after adopting the compatibility code.
✅ **`fct_orders`** — contract `urn:li:dataContract:75ac3dd7-5923-4747-8454-2db660c89206` written (upserted), status **PROPOSED** — approving it = merging this PR after adopting the compatibility code.

### Writeback 2 — generated compatibility code (mergeable)

**`models/compat/fct_orders_compat.sql`**
```sql
-- Generated by Downstream Impact Guardian.
-- Purpose: preserve the pre-PR contract of `fct_orders` for downstream
-- consumers while they migrate. Safe to merge as-is; delete once every
-- consumer found in DataHub lineage has moved off the old shape.
{{ config(materialized='view') }}

select
    order_id,
    customer_id,
    country,
    order_date,
    order_status,
    order_amount_usd as order_total,
    currency,
    is_fulfilled
from {{ ref('fct_orders') }}
```

**`models/compat/fct_orders_compat.yml`**
```yaml
version: 2

models:
  - name: fct_orders_compat
    description: >
      Backward-compatibility view generated by Downstream Impact
      Guardian. Exposes the pre-change contract of fct_orders.
    columns:
      - name: order_total
        description: Preserved from the old contract.
        tests: [not_null]
```

**`models/compat/revenue_daily_legacy.sql`**
```sql
-- Generated by Downstream Impact Guardian.
-- Purpose: preserve the pre-PR contract of `revenue_daily` for downstream
-- consumers while they migrate. Safe to merge as-is; delete once every
-- consumer found in DataHub lineage has moved off the old shape.
{{ config(materialized='view') }}

-- Gold: daily revenue rollup. Gross revenue counts every non-cancelled
-- order, including refunded ones (refunds are netted out elsewhere) —
-- this is the definition the "Gross Revenue" glossary term encodes.
select
    order_date,
    count(*)                                   as order_count,
    sum(order_total)                           as gross_revenue,
    avg(order_total)                           as avg_order_value
from {{ ref('fct_orders_compat') }}
where order_status != 'cancelled'
group by order_date
```

**`models/compat/revenue_daily_legacy.yml`**
```yaml
version: 2

models:
  - name: revenue_daily_legacy
    description: >
      Pre-PR definition of revenue_daily, preserved verbatim
      by Downstream Impact Guardian — consumers pinned to the old metric definition keep a working ref.
```

Drop these files into `models/compat/`, run `dbt build --select fct_orders_compat revenue_daily_legacy`, and downstream consumers keep working while they migrate.

---
_Generated by [Downstream Impact Guardian](https://github.com/jwlai-cloud/fiction-retail-dbt) · reads DataHub for what's live, the PR for what's proposed · never ingests hypothetical state._
