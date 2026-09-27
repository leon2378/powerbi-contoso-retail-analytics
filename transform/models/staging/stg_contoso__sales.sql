with source as (

    select * from {{ source('contoso', 'sales') }}

),

renamed as (

    select
        cast(OrderKey as bigint)              as order_key,
        cast(LineNumber as integer)           as line_number,
        cast(OrderDate as date)               as order_date,
        cast(DeliveryDate as date)            as delivery_date,
        cast(CustomerKey as integer)          as customer_key,
        cast(StoreKey as integer)             as store_key,
        cast(ProductKey as integer)           as product_key,
        cast(Quantity as integer)             as quantity,
        cast(UnitPrice as decimal(18, 4))     as unit_price_usd,
        cast(NetPrice as decimal(18, 4))      as net_price_usd,
        cast(UnitCost as decimal(18, 4))      as unit_cost_usd,
        upper(trim(CurrencyCode))             as currency_code,
        cast(ExchangeRate as decimal(18, 6))  as exchange_rate

    from source

)

select * from renamed
