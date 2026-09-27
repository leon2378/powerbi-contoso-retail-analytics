{#
    The online store has no country of its own. It gets the pseudo-country ONLINE so that
    the budget and row-level security, which both work at store-country grain, can address it.
#}
with stores as (

    select * from {{ ref('stg_contoso__stores') }}

)

select
    store_key,
    store_code,
    store_name,
    case when is_online then 'Online' else 'Physical' end                  as channel,
    case when is_online then 'ONLINE' else coalesce(country_code, 'N/A') end as country_code,
    case when is_online then 'Online' else coalesce(country_name, 'N/A') end as country_name,
    case when is_online then 'Online' else coalesce(state_name, 'N/A') end   as state_name,
    open_date,
    close_date,
    square_meters,
    coalesce(status, case when close_date is not null then 'Closed' else 'Open' end) as status

from stores
