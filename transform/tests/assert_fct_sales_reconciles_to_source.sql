-- Totals in the fact table must match the raw source exactly (no rows lost or duplicated in
-- staging or the mart). Returns a row, and therefore fails, when they drift.
with source_totals as (

    select
        count(*)                                                    as line_count,
        sum(cast(Quantity as bigint))                               as quantity,
        sum(cast(Quantity * NetPrice as decimal(38, 4)))            as net_amount
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
   or abs(s.net_amount - m.net_amount) > 1
