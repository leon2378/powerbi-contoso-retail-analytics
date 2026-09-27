{#
    Data minimisation: street address, title, company and vehicle are dropped here because no
    report needs them. Names are synthetic, but the model is built as if they were real PII.
#}
with source as (

    select * from {{ source('contoso', 'customer') }}

),

renamed as (

    select
        cast(CustomerKey as integer)                          as customer_key,
        concat_ws(' ', trim(GivenName), trim(Surname))        as customer_name,
        case lower(trim(Gender))
            when 'male' then 'Male'
            when 'female' then 'Female'
            else 'Unknown'
        end                                                   as gender,
        cast(Birthday as date)                                as birth_date,
        cast(Age as integer)                                  as age,
        nullif(trim(Occupation), '')                          as occupation,
        trim(City)                                            as city,
        trim(State)                                           as state_code,
        trim(StateFull)                                       as state_name,
        trim(ZipCode)                                         as postal_code,
        upper(trim(Country))                                  as country_code,
        trim(CountryFull)                                     as country_name,
        trim(Continent)                                       as continent,
        cast(Latitude as double)                              as latitude,
        cast(Longitude as double)                             as longitude

    from source

)

select * from renamed
