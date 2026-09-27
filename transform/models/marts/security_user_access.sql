{#
    User -> store-country entitlements used by the Power BI "Regional Manager" RLS role.
    Seeded here for the demo. In production, source this from your entitlement system
    (e.g. an Entra ID group export) instead of a CSV in the repo.
#}
select distinct
    lower(trim(user_principal_name)) as user_principal_name,
    upper(trim(country_code))        as country_code
from {{ ref('rls_user_access') }}
