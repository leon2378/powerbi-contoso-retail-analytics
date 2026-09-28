# Data dictionary

Generated from the semantic model by `scripts/generate_data_dictionary.py`. Do not edit by hand:
change the `///` descriptions in the TMDL files instead.

## Measures

### Budget

| Measure | Description | Format |
|---|---|---|
| **Budget Amount** | Budget in USD. The budget exists at month x category x store-country grain, so this returns BLANK whenever the report filters below that grain (single days, subcategories, products, stores or any customer attribute) rather than showing a misleading total. | `\$#,0` |
| **Budget to Date** | Budget for months that have started (up to the last order date), so it can be compared with actuals. Future months' budget is excluded; use [Budget Amount] to show the full plan. | `\$#,0` |
| **Sales in Budget Months** | Sales Amount for months that have a budget. The first year of history has no budget, so it is excluded from budget comparisons. | `\$#,0` |
| **Sales vs Budget** | Actuals minus budget over the same months: [Sales in Budget Months] - [Budget to Date]. BLANK where no budget applies. | `+\$#,0;-\$#,0;\$#,0` |
| **Sales vs Budget %** | Variance to budget as a share of budget, comparing the same months on both sides. | `+0.0%;-0.0%;0.0%` |
| **Categories Below Budget** | Product categories with sales below budget in the selected period (0 when all are on or above plan). BLANK where no budget applies. | `#,0` |

<details><summary>DAX: Budget Amount</summary>

```dax
VAR _IsDateAtBudgetGrain =
    COUNTROWS ( 'Date' )
        = CALCULATE ( COUNTROWS ( 'Date' ), ALL ( 'Date' ), VALUES ( 'Date'[Year Month Number] ) )
VAR _IsProductAtBudgetGrain =
    COUNTROWS ( 'Product' )
        = CALCULATE ( COUNTROWS ( 'Product' ), ALL ( 'Product' ), VALUES ( 'Product'[Category Key] ) )
VAR _IsStoreAtBudgetGrain =
    COUNTROWS ( Store )
        = CALCULATE ( COUNTROWS ( Store ), ALL ( Store ), VALUES ( Store[Country Code] ) )
VAR _IsCustomerUnfiltered =
    NOT ISCROSSFILTERED ( Customer )
RETURN
    IF (
        _IsDateAtBudgetGrain && _IsProductAtBudgetGrain && _IsStoreAtBudgetGrain && _IsCustomerUnfiltered,
        SUM ( Budget[Budget Amount] )
    )
```

</details>

<details><summary>DAX: Budget to Date</summary>

```dax
SUMX (
    FILTER (
        VALUES ( 'Date'[Year Month Number] ),
        CALCULATE ( COUNTROWS ( 'Date' ), 'Date'[Date With Sales] = TRUE ) > 0
    ),
    [Budget Amount]
)
```

</details>

<details><summary>DAX: Sales in Budget Months</summary>

```dax
CALCULATE (
    [Sales Amount],
    FILTER ( VALUES ( 'Date'[Year Month Number] ), NOT ISBLANK ( [Budget Amount] ) )
)
```

</details>

<details><summary>DAX: Sales vs Budget</summary>

```dax
VAR _Budget = [Budget to Date]
RETURN
    IF ( NOT ISBLANK ( _Budget ), [Sales in Budget Months] - _Budget )
```

</details>

<details><summary>DAX: Sales vs Budget %</summary>

```dax
VAR _Budget = [Budget to Date]
RETURN
    DIVIDE ( [Sales in Budget Months] - _Budget, _Budget )
```

</details>

<details><summary>DAX: Categories Below Budget</summary>

```dax
IF (
    NOT ISBLANK ( [Budget to Date] ),
    COUNTROWS ( FILTER ( VALUES ( 'Product'[Category] ), [Sales vs Budget] < 0 ) ) + 0
)
```

</details>

### Delivery

| Measure | Description | Format |
|---|---|---|
| **Avg Delivery Days** | Average days between order and delivery, per order line. | `0.0` |
| **Sales Amount by Delivery Date** | Sales Amount by delivery date instead of order date (activates the inactive relationship). | `\$#,0` |

<details><summary>DAX: Avg Delivery Days</summary>

```dax
AVERAGE ( Sales[Delivery Days] )
```

</details>

<details><summary>DAX: Sales Amount by Delivery Date</summary>

```dax
CALCULATE (
    [Sales Amount],
    USERELATIONSHIP ( Sales[Delivery Date], 'Date'[Date] )
)
```

</details>

### Margin

| Measure | Description | Format |
|---|---|---|
| **Total Cost** | Product cost of the units sold, in USD. | `\$#,0` |
| **Margin** | Sales Amount minus Total Cost. | `\$#,0` |
| **Margin %** | Margin as a share of Sales Amount. | `0.0%` |

<details><summary>DAX: Total Cost</summary>

```dax
SUM ( Sales[Cost Amount] )
```

</details>

<details><summary>DAX: Margin</summary>

```dax
[Sales Amount] - [Total Cost]
```

</details>

<details><summary>DAX: Margin %</summary>

```dax
DIVIDE ( [Margin], [Sales Amount] )
```

</details>

### Orders & Customers

| Measure | Description | Format |
|---|---|---|
| **Orders** | Number of distinct orders. Every order has exactly one line 0, and its dates, customer, store and currency are the same on every line (a dbt test guards both). So unless products or Sales columns filter individual lines, counting line-0 rows equals the distinct count, and at 10M orders it is ~50x faster by month or year. Otherwise it falls back to DISTINCTCOUNT. | `#,0` |
| **Order Lines** | Number of order lines. | `#,0` |
| **Avg Order Value** | Average net sales per order. | `\$#,0.00` |
| **Customers** | Distinct customers who bought in the selected period. | `#,0` |
| **New Customers** | Customers whose first-ever order falls inside the selected period. | `#,0` |
| **Returning Customers** | Customers who bought in the period and had also bought before it. | `#,0` |
| **Sales per Customer** | Average net sales per buying customer. | `\$#,0.00` |
| **Repeat Customer %** | Share of buying customers who placed two or more orders in the selected period. Meaningful at any grain, unlike new/returning, where every customer is "new" over all time. | `0.0%` |
| **Orders per Customer** | Average number of orders per buying customer in the selected period. | `0.00` |
| **Cohort Size** | Customers acquired in the cohort year in context (Customer[Acquisition Cohort]), counted over that whole year regardless of the date filter. BLANK unless exactly one cohort is in context. | `#,0` |
| **Cohort Retention %** | Share of a cohort's customers who bought in the selected period: [Customers] / [Cohort Size]. Put Acquisition Cohort on rows and Year on columns for a retention triangle. | `0.0%` |

<details><summary>DAX: Orders</summary>

```dax
IF (
    ISCROSSFILTERED ( 'Product' ) || ISFILTERED ( Sales ),
    DISTINCTCOUNT ( Sales[Order Number] ),
    CALCULATE ( COUNTROWS ( Sales ), Sales[Line Number] = 0 )
)
```

</details>

<details><summary>DAX: Order Lines</summary>

```dax
COUNTROWS ( Sales )
```

</details>

<details><summary>DAX: Avg Order Value</summary>

```dax
DIVIDE ( [Sales Amount], [Orders] )
```

</details>

<details><summary>DAX: Customers</summary>

```dax
DISTINCTCOUNT ( Sales[Customer Key] )
```

</details>

<details><summary>DAX: New Customers</summary>

```dax
CALCULATE (
    [Customers],
    TREATAS ( VALUES ( 'Date'[Date] ), Customer[First Order Date] )
)
```

</details>

<details><summary>DAX: Returning Customers</summary>

```dax
[Customers] - [New Customers]
```

</details>

<details><summary>DAX: Sales per Customer</summary>

```dax
DIVIDE ( [Sales Amount], [Customers] )
```

</details>

<details><summary>DAX: Repeat Customer %</summary>

```dax
// Same line-0 shortcut as [Orders], written inline: one scan counts each customer's orders.
VAR _RepeatCustomers =
    IF (
        ISCROSSFILTERED ( 'Product' ) || ISFILTERED ( Sales ),
        COUNTROWS ( FILTER ( VALUES ( Sales[Customer Key] ), CALCULATE ( DISTINCTCOUNT ( Sales[Order Number] ) ) > 1 ) ),
        COUNTROWS ( FILTER ( VALUES ( Sales[Customer Key] ), CALCULATE ( COUNTROWS ( Sales ), Sales[Line Number] = 0 ) > 1 ) )
    )
RETURN
    DIVIDE ( _RepeatCustomers, [Customers] )
```

</details>

<details><summary>DAX: Orders per Customer</summary>

```dax
DIVIDE ( [Orders], [Customers] )
```

</details>

<details><summary>DAX: Cohort Size</summary>

```dax
VAR _Cohort = SELECTEDVALUE ( Customer[Acquisition Cohort] )
RETURN
    IF (
        NOT ISBLANK ( _Cohort ) && _Cohort <> "No purchase",
        CALCULATE ( [Customers], REMOVEFILTERS ( 'Date' ), 'Date'[Year] = VALUE ( _Cohort ) )
    )
```

</details>

<details><summary>DAX: Cohort Retention %</summary>

```dax
VAR _ActiveCustomers = [Customers]
RETURN
    IF ( NOT ISBLANK ( _ActiveCustomers ), DIVIDE ( _ActiveCustomers, [Cohort Size] ) )
```

</details>

### Products

| Measure | Description | Format |
|---|---|---|
| **Products Sold** | Distinct products with at least one sale in the selected period. | `#,0` |
| **Sales Mix %** | Share of Sales Amount across the products selected outside the visual (slicers and cross-filters still apply), e.g. each price band's slice of sales. A visual's rows add up to 100%. | `0.0%` |
| **Price Band Share %** | Share of Sales Amount by price band within the current product selection, e.g. one category. Removes the price band filter (and its sort column, which Power BI groups by too) from the denominator only, so the bands of a category add up to 100%. | `0.0%` |
| **Subcategory Sales Rank** | Where the product in context ranks by Sales Amount among the products of its subcategory that sold in the selected period, e.g. "#3 of 45". BLANK unless exactly one product with sales is in context. |  |

<details><summary>DAX: Products Sold</summary>

```dax
DISTINCTCOUNT ( Sales[Product Key] )
```

</details>

<details><summary>DAX: Sales Mix %</summary>

```dax
DIVIDE ( [Sales Amount], CALCULATE ( [Sales Amount], ALLSELECTED ( 'Product' ) ) )
```

</details>

<details><summary>DAX: Price Band Share %</summary>

```dax
DIVIDE (
    [Sales Amount],
    CALCULATE ( [Sales Amount], REMOVEFILTERS ( 'Product'[Price Band], 'Product'[Price Band Sort] ) )
)
```

</details>

<details><summary>DAX: Subcategory Sales Rank</summary>

```dax
VAR _Product = SELECTEDVALUE ( 'Product'[Product Name] )
VAR _Subcategory = SELECTEDVALUE ( 'Product'[Subcategory] )
VAR _SellingPeers =
    FILTER (
        CALCULATETABLE (
            VALUES ( 'Product'[Product Name] ),
            REMOVEFILTERS ( 'Product' ),
            'Product'[Subcategory] = _Subcategory
        ),
        NOT ISBLANK ( [Sales Amount] )
    )
RETURN
    IF (
        NOT ISBLANK ( _Product ) && NOT ISBLANK ( [Sales Amount] ),
        "#" & RANKX ( _SellingPeers, [Sales Amount] ) & " of " & COUNTROWS ( _SellingPeers )
    )
```

</details>

### Report Helpers

| Measure | Description | Format |
|---|---|---|
| **Budget Variance Color** | Bar colour for budget variance, from the theme's diverging pair: blue at or above budget, red below. Bound to a visual's fill as a field value, so the colour always matches the sign. |  |
| **Selected Product** | Header of the Product Detail drill-through page: the product in context, or a hint when there isn't exactly one. |  |
| **Selected Product Details** | Subheader of the Product Detail page, e.g. "Contoso · Computers › Laptops · $500-999 · list price $899.00 · standard cost $412.34". BLANK unless exactly one product is in context. |  |
| **Tooltip Title** | Header of the category tooltip page: the hovered subcategory with its category (e.g. from the Products scatter), otherwise the hovered category, or "All categories". |  |
| **Data Freshness** | Report-header freshness label, e.g. "Data through 31 Dec 2025". Ignores all report filters. |  |
| **Selected Time Calculation Suffix** | " (YTD)"-style suffix naming the selected Time Intelligence item; BLANK for Current. |  |
| **Selected Metric Label** | Name of the metric picked in the Metric Selector field parameter plus the time calculation, e.g. "Margin % (YTD)". Used for dynamic visual titles. |  |
| **Title Metric by Year and Channel** | Dynamic title for the year x channel chart on the Sales Performance page. |  |
| **Title Metric by Weekday** | Dynamic title for the weekday chart on the Sales Performance page. |  |
| **Title Brand Performance** | Dynamic title for the brand table on the Sales Performance page (names the time calculation). |  |
| **Title Metric by Month** | Dynamic title for the monthly trend on the Sales Performance page. |  |

<details><summary>DAX: Budget Variance Color</summary>

```dax
IF ( [Sales vs Budget] < 0, "#E34948", "#2A78D6" )
```

</details>

<details><summary>DAX: Selected Product</summary>

```dax
SELECTEDVALUE ( 'Product'[Product Name], "Right-click a product and choose Drill through > Product Detail" )
```

</details>

<details><summary>DAX: Selected Product Details</summary>

```dax
IF (
    HASONEVALUE ( 'Product'[Product Name] ),
    SELECTEDVALUE ( 'Product'[Brand] ) & "  ·  "
        & SELECTEDVALUE ( 'Product'[Category] ) & " › " & SELECTEDVALUE ( 'Product'[Subcategory] ) & "  ·  "
        & SELECTEDVALUE ( 'Product'[Price Band] ) & "  ·  list price "
        & FORMAT ( SELECTEDVALUE ( 'Product'[List Price] ), "$#,0.00" ) & "  ·  standard cost "
        & FORMAT ( SELECTEDVALUE ( 'Product'[Standard Cost] ), "$#,0.00" )
)
```

</details>

<details><summary>DAX: Tooltip Title</summary>

```dax
VAR _Category = SELECTEDVALUE ( 'Product'[Category] )
VAR _Subcategory = SELECTEDVALUE ( 'Product'[Subcategory] )
RETURN
    IF (
        ISFILTERED ( 'Product'[Subcategory] ) && NOT ISBLANK ( _Subcategory ),
        _Subcategory & "  ·  " & _Category,
        COALESCE ( _Category, "All categories" )
    )
```

</details>

<details><summary>DAX: Data Freshness</summary>

```dax
VAR _LastOrderDate =
    CALCULATE ( MAX ( Sales[Order Date] ), REMOVEFILTERS () )
RETURN
    "Data through " & FORMAT ( _LastOrderDate, "d mmm yyyy" )
```

</details>

<details><summary>DAX: Selected Time Calculation Suffix</summary>

```dax
VAR _TimeCalculation = SELECTEDVALUE ( 'Time Intelligence'[Time Calculation], "Current" )
RETURN
    IF ( _TimeCalculation <> "Current", " (" & _TimeCalculation & ")" )
```

</details>

<details><summary>DAX: Selected Metric Label</summary>

```dax
// A field parameter's display column forms a composite key with its hidden fields column,
// so SELECTEDVALUE/VALUES on [Metric] alone raises an error. Read both columns together.
VAR _Selected =
    SUMMARIZE ( 'Metric Selector', 'Metric Selector'[Metric], 'Metric Selector'[Metric Fields] )
VAR _Metric =
    IF ( COUNTROWS ( _Selected ) = 1, MAXX ( _Selected, 'Metric Selector'[Metric] ), "Sales Amount" )
RETURN
    _Metric & [Selected Time Calculation Suffix]
```

</details>

<details><summary>DAX: Title Metric by Year and Channel</summary>

```dax
[Selected Metric Label] & " by year and channel"
```

</details>

<details><summary>DAX: Title Metric by Weekday</summary>

```dax
[Selected Metric Label] & " by weekday"
```

</details>

<details><summary>DAX: Title Brand Performance</summary>

```dax
"Brand performance" & [Selected Time Calculation Suffix]
```

</details>

<details><summary>DAX: Title Metric by Month</summary>

```dax
[Selected Metric Label] & " by month"
```

</details>

### Report Helpers\Alt Text

| Measure | Description | Format |
|---|---|---|
| **Alt Text Executive KPIs** | Screen-reader description of the Executive Overview KPI cards, with the current values. |  |
| **Alt Text Customers KPIs** | Screen-reader description of the Customers page KPI cards, with the current values. |  |
| **Alt Text Products KPIs** | Screen-reader description of the Products page KPI cards, with the current values. |  |
| **Alt Text Stores KPIs** | Screen-reader description of the Stores & Channels KPI cards, with the current values. |  |
| **Alt Text Budget KPIs** | Screen-reader description of the Budget Variance KPI cards, with the current values. |  |
| **Alt Text Product Detail KPIs** | Screen-reader description of the Product Detail header and KPI cards, with the current product and values. |  |
| **Alt Text Tooltip KPIs** | Screen-reader description of the category tooltip's KPI cards, with the hovered category and values. |  |

<details><summary>DAX: Alt Text Executive KPIs</summary>

```dax
"Sales " & FORMAT ( DIVIDE ( [Sales Amount], 1e6 ), "$#,0.0" ) & " million"
    & ", margin " & FORMAT ( [Margin %], "0.0%" )
    & ", " & FORMAT ( [Orders], "#,0" ) & " orders, " & FORMAT ( [Customers], "#,0" ) & " customers"
    & ", sales vs budget " & FORMAT ( [Sales vs Budget %], "+0.0%;-0.0%;0.0%" ) & "."
```

</details>

<details><summary>DAX: Alt Text Customers KPIs</summary>

```dax
FORMAT ( [Customers], "#,0" ) & " customers, "
    & FORMAT ( [Repeat Customer %], "0.0%" ) & " of them bought more than once, "
    & FORMAT ( [Orders per Customer], "0.00" ) & " orders and "
    & FORMAT ( [Sales per Customer], "$#,0" ) & " in sales per customer."
```

</details>

<details><summary>DAX: Alt Text Products KPIs</summary>

```dax
"Sales " & FORMAT ( DIVIDE ( [Sales Amount], 1e6 ), "$#,0.0" ) & " million"
    & ", margin " & FORMAT ( DIVIDE ( [Margin], 1e6 ), "$#,0.0" ) & " million" & " (" & FORMAT ( [Margin %], "0.0%" ) & ")"
    & ", average selling price " & FORMAT ( [Avg Selling Price], "$#,0.00" )
    & ", " & FORMAT ( [Products Sold], "#,0" ) & " products sold."
```

</details>

<details><summary>DAX: Alt Text Stores KPIs</summary>

```dax
"Sales " & FORMAT ( DIVIDE ( [Sales Amount], 1e6 ), "$#,0.0" ) & " million"
    & ", " & FORMAT ( [Online Sales %], "0.0%" ) & " online, "
    & FORMAT ( [Open Stores], "#,0" ) & " physical stores open, "
    & FORMAT ( [Sales per Store], "$#,0" ) & " per store and "
    & FORMAT ( [Sales per Square Meter], "$#,0" ) & " per square metre of store space."
```

</details>

<details><summary>DAX: Alt Text Budget KPIs</summary>

```dax
"Sales " & FORMAT ( DIVIDE ( [Sales in Budget Months], 1e6 ), "$#,0.0" ) & " million" & " against a budget of " & FORMAT ( DIVIDE ( [Budget to Date], 1e6 ), "$#,0.0" ) & " million"
    & ": " & FORMAT ( DIVIDE ( [Sales vs Budget], 1e6 ), "+$#,0.0;-$#,0.0;$0.0" ) & " million ("
    & FORMAT ( [Sales vs Budget %], "+0.0%;-0.0%;0.0%" ) & "), "
    & FORMAT ( [Categories Below Budget], "0" ) & " of " & COUNTROWS ( VALUES ( 'Product'[Category] ) ) & " categories below budget."
```

</details>

<details><summary>DAX: Alt Text Product Detail KPIs</summary>

```dax
IF (
    HASONEVALUE ( 'Product'[Product Name] ),
    [Selected Product] & ": sales " & FORMAT ( [Sales Amount], "$#,0" )
        & ", " & FORMAT ( [Quantity], "#,0" ) & " units, average price " & FORMAT ( [Avg Selling Price], "$#,0.00" )
        & ", margin " & FORMAT ( [Margin %], "0.0%" ) & ", " & FORMAT ( [Customers], "#,0" ) & " customers"
        & ", rank " & [Subcategory Sales Rank] & " in its subcategory.",
    [Selected Product]
)
```

</details>

<details><summary>DAX: Alt Text Tooltip KPIs</summary>

```dax
[Tooltip Title] & ": sales " & FORMAT ( DIVIDE ( [Sales Amount], 1e6 ), "$#,0.0" ) & " million"
    & ", margin " & FORMAT ( DIVIDE ( [Margin], 1e6 ), "$#,0.0" ) & " million" & " (" & FORMAT ( [Margin %], "0.0%" ) & ")."
```

</details>

### Sales

| Measure | Description | Format |
|---|---|---|
| **Sales Amount** | Net sales after discounts, in USD. The headline revenue KPI. | `\$#,0` |
| **Gross Sales** | Sales at list price before discounts, in USD. | `\$#,0` |
| **Discount Amount** | Value given away as discounts: Gross Sales minus Sales Amount. | `\$#,0` |
| **Discount %** | Share of gross sales given away as discounts. | `0.0%` |
| **Quantity** | Units sold. | `#,0` |
| **Avg Selling Price** | Average net price per unit sold. | `\$#,0.00` |
| **Sales Amount (Local Currency)** | Net sales in the order currency. Returns BLANK unless exactly one currency is in context, because amounts in different currencies cannot be added up. | dynamic |

<details><summary>DAX: Sales Amount</summary>

```dax
SUM ( Sales[Net Amount] )
```

</details>

<details><summary>DAX: Gross Sales</summary>

```dax
SUM ( Sales[Gross Amount] )
```

</details>

<details><summary>DAX: Discount Amount</summary>

```dax
[Gross Sales] - [Sales Amount]
```

</details>

<details><summary>DAX: Discount %</summary>

```dax
DIVIDE ( [Discount Amount], [Gross Sales] )
```

</details>

<details><summary>DAX: Quantity</summary>

```dax
SUM ( Sales[Quantity] )
```

</details>

<details><summary>DAX: Avg Selling Price</summary>

```dax
DIVIDE ( [Sales Amount], [Quantity] )
```

</details>

<details><summary>DAX: Sales Amount (Local Currency)</summary>

```dax
IF (
    HASONEVALUE ( Sales[Currency Code] ),
    SUM ( Sales[Net Amount (Local)] )
)
```

</details>

### Stores & Channels

| Measure | Description | Format |
|---|---|---|
| **Online Sales %** | Share of Sales Amount sold through the online store. Respects a Channel filter, so with only physical stores selected it shows 0%. | `0.0%` |
| **Open Stores** | Physical stores open at the end of the selected period: opened on or before it and not closed by then. Stores have no relationship to 'Date', so the period end is read from 'Date' directly. | `#,0` |
| **Sales per Store** | Average Sales Amount per physical store that sold in the selected period. | `\$#,0` |
| **Sales per Square Meter** | Physical-store Sales Amount per square metre of selling space, counting the space of the stores that sold in the selected period. It covers the whole period, so compare like-for-like periods. | `\$#,0` |

<details><summary>DAX: Online Sales %</summary>

```dax
DIVIDE ( CALCULATE ( [Sales Amount], KEEPFILTERS ( Store[Channel] = "Online" ) ) + 0, [Sales Amount] )
```

</details>

<details><summary>DAX: Open Stores</summary>

```dax
VAR _PeriodEnd = MAX ( 'Date'[Date] )
RETURN
    COUNTROWS (
        FILTER (
            Store,
            Store[Channel] = "Physical"
                && Store[Open Date] <= _PeriodEnd
                && ( ISBLANK ( Store[Close Date] ) || Store[Close Date] > _PeriodEnd )
        )
    )
```

</details>

<details><summary>DAX: Sales per Store</summary>

```dax
VAR _SellingStores =
    COUNTROWS ( FILTER ( Store, Store[Channel] = "Physical" && NOT ISBLANK ( [Sales Amount] ) ) )
RETURN
    DIVIDE ( CALCULATE ( [Sales Amount], KEEPFILTERS ( Store[Channel] = "Physical" ) ), _SellingStores )
```

</details>

<details><summary>DAX: Sales per Square Meter</summary>

```dax
VAR _SellingArea =
    SUMX (
        FILTER ( Store, Store[Channel] = "Physical" && NOT ISBLANK ( [Sales Amount] ) ),
        Store[Square Meters]
    )
RETURN
    DIVIDE ( CALCULATE ( [Sales Amount], KEEPFILTERS ( Store[Channel] = "Physical" ) ), _SellingArea )
```

</details>

## Tables

### Sales

Order lines (dbt mart fct_sales). Grain: one row per order line. Amounts in USD. Loaded with incremental refresh: yearly archive partitions plus monthly partitions for recent data.

| Column | Type | Description |
|---|---|---|
| Order Number | int64 | Order number. Use it for detail tables and drill-through. |
| Currency Code | string | ISO currency of the order. Filter to one currency to use [Sales Amount (Local Currency)]. |

### Budget (hidden)

Monthly budget at category x store-country grain (dbt mart fct_sales_budget). Related to Product and Store through many-to-many relationships at that coarser grain. Use the [Budget Amount] measure, which blanks out below budget grain.

### Date

Calendar (dbt mart dim_date), marked as the model's date table. Covers complete years.

| Column | Type | Description |
|---|---|---|
| Date | dateTime |  |
| Year | int64 |  |
| Quarter | string |  |
| Year Quarter | string |  |
| Month | string |  |
| Month Short | string |  |
| Year Month | string |  |
| Month Start Date | dateTime | First day of the month. Use it on line and area charts for a continuous monthly axis. |
| Day of Week | string |  |
| Day of Week Short | string |  |
| Day of Month | int64 |  |
| ISO Week | int64 |  |
| Is Weekend | boolean |  |

### Customer

Customers (dbt mart dim_customer). Street-level PII is removed upstream.

| Column | Type | Description |
|---|---|---|
| Customer Name | string |  |
| Gender | string |  |
| Age | int64 |  |
| Age Band | string |  |
| Occupation | string |  |
| City | string |  |
| State | string |  |
| Postal Code | string |  |
| Country | string |  |
| Continent | string |  |
| Latitude | double |  |
| Longitude | double |  |
| First Order Date | dateTime | Date of the customer's first order ever. Drives [New Customers]. |
| Acquisition Cohort | string | Year of first purchase ("No purchase" for prospects). Use for cohort analysis. |
| Has Purchased | boolean |  |

### Product

Products (dbt mart dim_product). Category is the budget grain.

| Column | Type | Description |
|---|---|---|
| Product Code | string |  |
| Product Name | string |  |
| Manufacturer | string |  |
| Brand | string |  |
| Color | string |  |
| Category | string |  |
| Subcategory | string |  |
| List Price | decimal | Current list price in USD (attribute, not additive). |
| Standard Cost | decimal | Current standard cost in USD (attribute, not additive). |
| Price Band | string |  |

### Store

Stores (dbt mart dim_store), including the online store (Channel = Online, Country Code = ONLINE). Row-level security filters this table by Country Code.

| Column | Type | Description |
|---|---|---|
| Store Code | int64 |  |
| Store Name | string |  |
| Channel | string |  |
| Country Code | string |  |
| Country | string |  |
| State | string |  |
| Open Date | dateTime |  |
| Close Date | dateTime |  |
| Square Meters | int64 |  |
| Status | string |  |

### Time Intelligence

Time-intelligence variants for any measure: put 'Time Calculation' on columns or in a slicer. Prior-year items only compare dates that have sales ('Date'[Date With Sales]), so a partial current year is compared like-for-like with the same span of the previous year.

| Column | Type | Description |
|---|---|---|
| Time Calculation | string |  |

### Metric Selector

Field parameter: lets report users switch the measure shown by a visual with a slicer.

| Column | Type | Description |
|---|---|---|
| Metric | string |  |

### Security Access (hidden)

RLS entitlements: which store countries each user may see (dbt mart security_user_access). Deliberately has no relationships; the 'Regional Manager' role reads it with USERPRINCIPALNAME().
