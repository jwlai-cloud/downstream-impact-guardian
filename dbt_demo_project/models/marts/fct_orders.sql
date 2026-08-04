-- Gold: order-level fact consumed by finance and marketing.
select
    o.order_id,
    o.customer_id,
    c.country,
    o.order_date,
    o.order_status,
    o.order_total as order_amount_usd,
    o.currency,
    o.order_status in ('completed', 'shipped') as is_fulfilled
from {{ ref('stg_orders') }} o
join {{ ref('stg_customers') }} c using (customer_id)
