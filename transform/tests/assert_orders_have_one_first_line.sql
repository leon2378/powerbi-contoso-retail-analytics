-- The Orders measure counts each order's line 0 when no product or line-level filter applies, which
-- is much faster than a distinct count at 10M orders. That equals the distinct count only if every
-- order has exactly one line 0 and its dates, customer, store and currency are the same on every
-- line. Returns the orders that break either rule.
select order_key
from {{ ref('fct_sales') }}
group by order_key
having count(*) filter (where line_number = 0) <> 1
    or count(distinct order_date) > 1
    or count(distinct delivery_date) > 1
    or count(distinct customer_key) > 1
    or count(distinct store_key) > 1
    or count(distinct currency_code) > 1
