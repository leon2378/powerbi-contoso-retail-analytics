-- Totals in the fact table must match the raw source exactly (no rows lost or duplicated in
-- staging or the mart). Returns a row, and therefore fails, when they drift.
--
-- The source stores prices with 5 decimals and the mart rounds them to 4, as staging does. The
-- source side applies the same per-line rounding, so the amounts must match exactly and no
-- tolerance is needed. (Summing unrounded prices drifted by ~$50 on $23.2bn at 10M orders,
-- which a fixed $1 tolerance reported as a failure.)
with source_totals as (

    select
        count(*)                                                    as line_count,
        sum(cast(Quantity as bigint))                               as quantity,
        sum(cast(Quantity * cast(NetPrice as decimal(18, 4)) as decimal(18, 4))) as net_amount
    from {{ source('contoso', 'sales') }}

),

mart_totals as (

    select
        count(*)             as line_count,
        sum(quantity)        as quantity,
        sum(net_amount_usd)  as net_amount
    from {{ ref('fct_sales') }}

)

select *
from source_totals as s
cross join mart_totals as m
where s.line_count <> m.line_count
   or s.quantity <> m.quantity
   or s.net_amount <> m.net_amount
