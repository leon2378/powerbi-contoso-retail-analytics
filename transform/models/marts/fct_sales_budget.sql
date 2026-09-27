{#
    Synthetic sales budget, because Contoso ships without one.
    Grain: month x product category x store country.
    Budget = the same month last year x (1 + the category growth target from the
    budget_growth_targets seed). It only covers months inside the date dimension, so every row
    joins to the calendar. In a real deployment this model would read the planning system instead.
#}
with actuals as (

    select
        date_trunc('month', s.order_date)::date  as month_start_date,
        p.category_key,
        p.category_name,
        st.country_code                           as store_country_code,
        sum(s.net_amount_usd)                     as net_sales_usd
    from {{ ref('fct_sales') }} as s
    inner join {{ ref('dim_product') }} as p on s.product_key = p.product_key
    inner join {{ ref('dim_store') }} as st on s.store_key = st.store_key
    group by all

),

targets as (

    select * from {{ ref('budget_growth_targets') }}

),

calendar_end as (

    select max(date) as last_date from {{ ref('dim_date') }}

)

select
    (a.month_start_date + interval 1 year)::date                     as month_start_date,
    a.category_key,
    a.store_country_code,
    cast(
        round(a.net_sales_usd * (1 + coalesce(t.growth_rate, {{ var('default_budget_growth') }})), 2)
        as decimal(18, 4)
    )                                                                 as budget_amount_usd

from actuals as a
left join targets as t
    on a.category_name = t.category_name
cross join calendar_end as c
where (a.month_start_date + interval 1 year)::date <= c.last_date
