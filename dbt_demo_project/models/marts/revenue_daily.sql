-- Gold: daily revenue rollup. Gross revenue counts every non-cancelled
-- order, including refunded ones (refunds are netted out elsewhere) —
-- this is the definition the "Gross Revenue" glossary term encodes.
select
    order_date,
    count(*)                                   as order_count,
    sum(order_total)                           as gross_revenue,
    avg(order_total)                           as avg_order_value
from {{ ref('fct_orders') }}
where order_status != 'cancelled'
group by order_date
