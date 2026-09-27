{#
    Calendar dimension covering whole years from the first order to the last delivery, so
    time-intelligence functions in DAX always see complete years.
    date_with_sales flags dates up to the last order date; the Time Intelligence calculation
    group uses it to stop previous-year comparisons at the same point in the year.
#}
with bounds as (

    select
        date_trunc('year', min(order_date))::date                                   as first_date,
        (date_trunc('year', max(delivery_date)) + interval 1 year - interval 1 day)::date as last_date,
        max(order_date)                                                             as last_order_date
    from {{ ref('stg_contoso__sales') }}

),

spine as (

    select
        cast(unnest(generate_series(first_date::timestamp, last_date::timestamp, interval 1 day)) as date) as date_day,
        last_order_date
    from bounds

)

select
    date_day                                                  as date,
    cast(strftime(date_day, '%Y%m%d') as integer)             as date_key,
    cast(year(date_day) as integer)                           as year,
    cast(quarter(date_day) as integer)                        as quarter_number,
    concat('Q', quarter(date_day))                            as quarter,
    concat(year(date_day), ' Q', quarter(date_day))           as year_quarter,
    cast(year(date_day) * 10 + quarter(date_day) as integer)  as year_quarter_number,
    cast(month(date_day) as integer)                          as month_number,
    strftime(date_day, '%B')                                  as month_name,
    strftime(date_day, '%b')                                  as month_short,
    strftime(date_day, '%b %Y')                               as year_month,
    cast(year(date_day) * 100 + month(date_day) as integer)   as year_month_number,
    date_trunc('month', date_day)::date                       as month_start_date,
    cast(isodow(date_day) as integer)                         as day_of_week_number,
    strftime(date_day, '%A')                                  as day_of_week,
    strftime(date_day, '%a')                                  as day_of_week_short,
    cast(day(date_day) as integer)                            as day_of_month,
    cast(weekofyear(date_day) as integer)                     as iso_week_number,
    isodow(date_day) in (6, 7)                                as is_weekend,
    date_day <= last_order_date                               as date_with_sales

from spine
