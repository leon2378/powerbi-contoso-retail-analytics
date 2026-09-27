with customers as (

    select * from {{ ref('stg_contoso__customers') }}

),

first_orders as (

    select
        customer_key,
        min(order_date) as first_order_date
    from {{ ref('stg_contoso__sales') }}
    group by customer_key

)

select
    c.customer_key,
    c.customer_name,
    c.gender,
    c.age,
    case
        when c.age is null then 'Unknown'
        when c.age < 25 then 'Under 25'
        when c.age < 35 then '25-34'
        when c.age < 45 then '35-44'
        when c.age < 55 then '45-54'
        when c.age < 65 then '55-64'
        else '65+'
    end                                                          as age_band,
    case
        when c.age is null then 99
        when c.age < 25 then 1
        when c.age < 35 then 2
        when c.age < 45 then 3
        when c.age < 55 then 4
        when c.age < 65 then 5
        else 6
    end                                                          as age_band_sort,
    c.occupation,
    c.city,
    c.state_code,
    c.state_name,
    c.postal_code,
    c.country_code,
    c.country_name,
    c.continent,
    c.latitude,
    c.longitude,
    f.first_order_date,
    coalesce(cast(year(f.first_order_date) as varchar), 'No purchase') as acquisition_cohort,
    f.first_order_date is not null                               as has_purchased

from customers as c
left join first_orders as f
    on c.customer_key = f.customer_key
