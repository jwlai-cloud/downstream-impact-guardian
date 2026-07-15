-- Bronze -> silver: light cleanup only.
select
    customer_id,
    trim(full_name)        as full_name,
    lower(email)           as email,
    upper(country)         as country,
    signup_date
from {{ ref('raw_customers') }}
