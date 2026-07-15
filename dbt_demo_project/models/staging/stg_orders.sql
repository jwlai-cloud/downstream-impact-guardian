-- Bronze -> silver: normalize statuses, keep one row per order.
select
    order_id,
    customer_id,
    order_date,
    lower(order_status)    as order_status,
    cast(order_total as numeric) as order_total,
    upper(currency)        as currency
from {{ ref('raw_orders') }}
