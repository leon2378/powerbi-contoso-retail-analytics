with source as (

    select * from {{ source('contoso', 'store') }}

),

renamed as (

    select
        cast(StoreKey as integer)                  as store_key,
        cast(StoreCode as integer)                 as store_code,
        trim(Description)                          as store_name,
        -- The generator models its single web shop as a store with GeoAreaKey = -1
        -- and CountryCode '--'.
        GeoAreaKey = -1                            as is_online,
        nullif(nullif(upper(trim(CountryCode)), ''), '--') as country_code,
        nullif(trim(CountryName), '')              as country_name,
        nullif(trim(State), '')                    as state_name,
        cast(OpenDate as date)                     as open_date,
        cast(CloseDate as date)                    as close_date,
        cast(SquareMeters as integer)              as square_meters,
        nullif(trim(Status), '')                   as status

    from source

)

select * from renamed
