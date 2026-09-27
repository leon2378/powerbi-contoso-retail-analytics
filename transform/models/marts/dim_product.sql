with products as (

    select * from {{ ref('stg_contoso__products') }}

)

select
    product_key,
    product_code,
    product_name,
    manufacturer,
    brand,
    color,
    category_key,
    category_name,
    subcategory_key,
    subcategory_name,
    list_price_usd,
    standard_cost_usd,
    case
        when list_price_usd < 100 then 'Under $100'
        when list_price_usd < 500 then '$100-499'
        when list_price_usd < 1000 then '$500-999'
        else '$1,000+'
    end as price_band,
    case
        when list_price_usd < 100 then 1
        when list_price_usd < 500 then 2
        when list_price_usd < 1000 then 3
        else 4
    end as price_band_sort

from products
