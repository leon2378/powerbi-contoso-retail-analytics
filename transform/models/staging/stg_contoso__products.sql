with source as (

    select * from {{ source('contoso', 'product') }}

),

renamed as (

    select
        cast(ProductKey as integer)          as product_key,
        trim(ProductCode)                    as product_code,
        trim(ProductName)                    as product_name,
        trim(Manufacturer)                   as manufacturer,
        trim(Brand)                          as brand,
        trim(Color)                          as color,
        cast(Price as decimal(18, 4))        as list_price_usd,
        cast(Cost as decimal(18, 4))         as standard_cost_usd,
        cast(CategoryKey as integer)         as category_key,
        trim(CategoryName)                   as category_name,
        cast(SubCategoryKey as integer)      as subcategory_key,
        trim(SubCategoryName)                as subcategory_name

    from source

)

select * from renamed
