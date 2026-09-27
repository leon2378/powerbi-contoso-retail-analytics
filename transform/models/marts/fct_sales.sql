{#
    Grain: one row per order line.
    Only additive amounts the semantic model needs are materialised; ratios (margin %, discount %,
    average selling price) are DAX measures so they aggregate correctly at any level.
#}
with sales as (

    select * from {{ ref('stg_contoso__sales') }}

)

select
    order_key,
    line_number,
    order_date,
    delivery_date,
    customer_key,
    store_key,
    product_key,
    currency_code,
    quantity,
    cast(quantity * unit_price_usd as decimal(18, 4))                  as gross_amount_usd,
    cast(quantity * net_price_usd as decimal(18, 4))                   as net_amount_usd,
    cast(quantity * unit_cost_usd as decimal(18, 4))                   as cost_amount_usd,
    cast(quantity * net_price_usd * exchange_rate as decimal(18, 4))   as net_amount_local,
    cast(date_diff('day', order_date, delivery_date) as integer)       as delivery_days

from sales
