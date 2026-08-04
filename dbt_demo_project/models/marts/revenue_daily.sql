-- Gold: daily revenue rollup. Gross revenue now only counts fulfilled
-- orders (completed/shipped) — refunded and pending orders are excluded.
select
    order_date,
    count(*)                                   as order_count,
    sum(order_amount_usd)                      as gross_revenue,
    avg(order_amount_usd)                      as avg_order_value
from {{ ref('fct_orders') }}
where order_status in ('completed', 'shipped')
group by order_date
