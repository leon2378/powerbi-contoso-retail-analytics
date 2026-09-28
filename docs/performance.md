# Performance at 10M orders

The report is built and screenshotted on the 100K-order dataset. This page records how the same
pipeline, model and report behave on SQLBI's 10M-order release, what that test found, and what
changed as a result.

## Test setup

| | |
|---|---|
| Data | Contoso V2 "10m": 9,887,613 orders, **23,719,935 order lines**, 1,679,846 customers, 2,517 products, 74 stores |
| Machine | Windows 11, 16 logical processors, 60 GB RAM, Power BI Desktop (Store app) |
| Report | All 7 pages clicked through once, plus the category tooltip and a drill-through to Product Detail |

## Results

| Step | Result |
|---|---|
| Download and extract (680 MB archive) | 101 s |
| `dbt build`: 11 models, 2 seeds and 45 tests (43 data tests, 2 unit tests) | **27 s** |
| Full refresh in Power BI Desktop (Home → Refresh) | **4 min 13 s** |
| Model size in memory (VertiPaq) | **845 MB**: Sales 634 MB, Customer 193 MB, everything else 18 MB |
| Largest columns | `Sales[Order Number]` 90 MB (plus its hierarchy), `Sales[Net Amount]` 90 MB, `Sales[Net Amount (Local)]` 90 MB, `Customer[Customer Name]` 57 MB |

### Report queries

Every DAX query the report sent during the click-through was recorded (118 queries, 87 distinct),
then each distinct query was replayed on its own: **cold** with the engine cache cleared, and **warm**
straight after. Replaying one at a time avoids the noise of a page's visuals waiting on each other.

| | Before | After |
|---|---|---|
| Queries under 1 s, cold | 66 of 87 (76%) | **81 of 87 (93%)** |
| 90th percentile, cold | 3.7 s | **0.83 s** |
| Slowest, cold | 4.1 s | 1.8 s |
| Median, cold | 40 ms | 36 ms |
| Warm: median / slowest | 6 ms / 0.97 s | 6 ms / 0.89 s |

## What the test found and what changed

**Distinct counts are cheap in total and expensive when grouped.** `[Orders]` for everything took
14 ms, but Orders by brand took 4.0 s cold and by month 1.75 s: counting 9.9M distinct order numbers
separately for every group is the costly part.

1. **`[Orders]` counts each order's line 0 when it can.** Every order has exactly one line 0, and its
   dates, customer, store and currency are the same on every line, so unless products or Sales columns
   filter individual lines, counting line-0 rows equals the distinct count. Orders by month dropped from
   1,752 ms to 37 ms, and by year × channel or weekday to about 22 ms, with identical results. With a
   product filter the measure falls back to `DISTINCTCOUNT`. A dbt test
   (`assert_orders_have_one_first_line`) guards both assumptions, so the shortcut can't silently go wrong
   if the source changes.
2. **`[Repeat Customer %]` uses the same shortcut inline**: one scan counts each customer's orders. 3.8 s
   → 1.8 s cold for the total, with identical results. It still has to hold one count per customer (1.7M
   of them) to test "two or more", which is why it remains the slowest query.
3. **The Sales Performance brand table shows Units instead of Orders.** A brand is a product filter, so
   Orders per brand always needs the full distinct count: 4.2 s cold. Units (quantity sold) per brand
   takes 36 ms and is as informative there. Orders stays in the metric tiles and everywhere else.

**Tried and rejected:** counting repeat customers by comparing each customer's first and last order
number (6.5 s, slower, because the engine evaluated it customer by customer), and counting distinct
customers over line-0 rows only (about 20% faster; not worth the extra complexity).

**Remaining above 1 s cold** (all under 0.9 s warm): six queries that count distinct customers among
1.7M. These are the Customers page KPI row (1.8 s, because of Repeat Customer %), the Customers metric
by month (1.3 s), the cohort heatmap (1.1 s) and new vs returning customers (1.1 s).

**A data-quality check that only failed at scale.** The test that reconciles the sales mart with the raw
source failed at 10M: row counts and quantities matched exactly, but revenue differed by $51.70 on
$23.2bn. The source stores prices with 5 decimals and the mart rounds them to 4; the test summed the
unrounded prices with a $1 tolerance, which 23.7M sub-cent roundings exceeded. It now rounds the source
exactly like the mart and requires an exact match, which is stricter and holds at any scale.

## Reproduce

```powershell
# Data and marts in their own folders, so the 100K working copy stays untouched
.venv\Scripts\python scripts\download_contoso.py --size 10m --raw-dir data\10m\raw
$env:CONTOSO_RAW_DIR = "data/10m/raw"; $env:CONTOSO_MARTS_DIR = "data/10m/marts"; $env:DUCKDB_PATH = "data/10m/contoso.duckdb"
.venv\Scripts\dbt build --project-dir transform --profiles-dir transform
.venv\Scripts\python scripts\set_model_source.py local --data-root "$PWD\data\10m\marts"

# Open powerbi\ContosoRetail.pbip, Home > Refresh, then measure with tools\PerfKit
# (the port is in %USERPROFILE%\Microsoft\Power BI Desktop Store App\AnalysisServicesWorkspaces\*\Data\msmdsrv.port.txt)
dotnet run --project tools\PerfKit -c Release -- trace <port> trace.jsonl stop.flag   # click through the report, then create stop.flag
dotnet run --project tools\PerfKit -c Release -- replay <port> trace.jsonl
dotnet run --project tools\PerfKit -c Release -- vertipaq <port>

# Back to the 100K working copy
.venv\Scripts\python scripts\set_model_source.py local
```
