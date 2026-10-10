# Report design guide

The report is 1280 × 720, built on a 16 px grid, with the **Contoso Executive** theme
(`StaticResources/RegisteredResources/ContosoExecutive.json`). Every page in the plan below is built: the six
main pages, the **Product detail** drill-through and the **Tooltip page**.

## Page plan

| Page | Question it answers | Suggested visuals | Model features it shows off |
|---|---|---|---|
| **Executive Overview** ✅ | How are we doing vs last year and vs budget? | KPI cards, sales vs budget trend, category YoY matrix, country bars | Time Intelligence calc group, grain-aware budget |
| **Sales Performance** ✅ | What drives revenue? | Metric tiles (**Metric Selector** field parameter) and a time-calculation dropdown drive a monthly trend, year × channel columns and a weekday profile; brand table; dynamic titles name the selected metric and time calculation | Field parameter, calc group in a slicer, slicers synced across pages |
| **Customers** ✅ | Are we acquiring and keeping customers? | KPI cards (Customers, Repeat Customer %, Orders and Sales per Customer), new vs returning by year, cohort retention heatmap (Acquisition Cohort × Year), age band × gender, customers by country | `New Customers`, `Cohort Retention %`, conditional-formatting colour scale |
| **Products** ✅ | What sells, at what price and margin? | KPI cards, full-width scatter of Sales Amount (log scale) vs Margin % per subcategory, top 10 products table (Top N filter), price band summary with data bars; Category slicer in the header | Price bands (sorted by a hidden column), `Sales Mix %` (`ALLSELECTED`), `Products Sold` |
| **Stores & Channels** ✅ | Where do we sell? | KPI cards, sales by channel and month, physical store sales by country (drill down to state), physical store table with open/close dates, sales per m² by country | Store hierarchy, `Open Stores` (date logic without a relationship), `Sales per Square Meter`, `Online Sales %`, visual-level filters, RLS (test with *View as*) |
| **Budget Variance** ✅ | Where are we off plan? | KPI cards, waterfall of *Sales vs Budget* by category, *Sales vs Budget %* by store country (bar colour from a measure), category × year heatmap on *Sales vs Budget %* that drills down to months | Many-to-many budget relationships, grain-aware `Budget Amount`, field-value conditional formatting, diverging colour scale |
| **Product detail** (drill-through) ✅ | Everything about one product | Back button; KPI card whose title and subtitle are the product name and attributes (measures); monthly trend; price, volume and margin by year; customers by age band and gender; sales by channel. Left visible, opening on the top seller, so it can be browsed and exported | Drill-through filter with `pageBinding`, filter context flows from the source page, `Subcategory Sales Rank` (`RANKX`) |
| **Tooltip page** ✅ | Context on hover | 400 × 384 page: KPI card titled with the hovered category or subcategory (`Tooltip Title`), mini monthly trend, price-band mix (`Price Band Share %`). Used by the Executive Overview category bars, the Budget Variance waterfall and the Products scatter | Report page tooltips (`pageBinding` type Tooltip, `visualTooltip` on the source visuals) |

## Colour system

Taken from a validated, colour-vision-deficiency-checked palette:

- **Categorical, in fixed order, never cycled:** `#2A78D6` blue, `#EB6834` orange, `#1BAF7A` aqua, `#EDA100` yellow,
  `#E87BA4` magenta, `#008300` green, `#4A3AA7` violet, `#E34948` red. With more than 8 series, fold the rest into
  "Other" or use small multiples.
- **Colour follows the entity, not its rank.** Pin important series colours (e.g. Actual = blue, Budget = orange)
  so filtering never repaints them.
- **Sequential** (heatmaps, conditional formatting): one hue, light → dark (`#CDE2FB` → `#104281`).
- **Diverging** (variance): blue ↔ red with a grey midpoint (`#F0EFEC`).
- **Status colours are reserved**: good `#0CA30C`, warning `#FAB219`, bad `#D03B3B`. Always pair them with an icon or a
  +/− sign, never colour alone, and never use them as a regular series colour.
- Aqua, yellow and magenta are below 3:1 contrast on white. Charts that use them need **data labels** or a
  table view.

## Chart rules

- **No dual-axis charts.** Two measures of different scale go into two charts or small multiples.
- Legends whenever there are 2+ series. Direct labels on bars; no label on every line point.
- Recessive gridlines (`#E6E5E1`), no axis titles when the visual title already says it.
- Titles say what the chart shows, with units: "Net sales vs budget by month (USD)".
- At most about 8 visuals per page. Filters go in the header row, not scattered.

## Accessibility checklist

- [x] Every visual has alt text (*Format → General → Alt text*): 69 visuals. The KPI rows and freshness labels use
      measures (display folder *Report Helpers\Alt Text*), so a screen reader hears the current values, e.g. "Sales
      $23.2 billion, margin 55.9%, …". `validate_report.py` fails CI when a visual has none or when typed alt text
      exceeds Power BI's 250 characters.
- [x] Tab order follows reading order (*View → Selection → Tab order*), on the web and the mobile layout.
      Power BI tabs from the highest `tabOrder` to the lowest, so the page title has the largest value.
      `validate_report.py` fails CI when a visual above, or to the left in the same row, comes later.
- [x] Information is never carried by colour alone: legends on every multi-series chart, direct labels, + and −
      signs on every variance, and a one-colour scatter with labelled points.
- [x] Text contrast ≥ 4.5:1. Ink `#0B0B0B` is 19.7:1 and `#52514E` 7.9:1 on white; dark text on the data-bar and
      heatmap tints is 9.3:1 or more. Data labels on orange bars are set to ink (6.2:1 inside the bar), because
      Power BI's automatic white label is only 3.2:1 there.
- [x] Keyboard-only walkthrough of every page, including slicers and drill-through, done in Power BI Desktop with
      the focused element logged through UI Automation (what a screen reader announces):
      - *Ctrl+F6* reaches the canvas on the page title, and the order follows the layout on all seven pages. Every
        visual announces its title and alt text; the KPI rows read their live values.
      - Dropdown slicers: *Ctrl+Right arrow* into the slicer, *Enter* opens the list, arrow keys and *Space* select,
        and *Clear selections* is reachable with *Tab*. Metric buttons: arrow keys between tiles, *Enter* selects.
      - Charts: *Ctrl+Right arrow*, then *Tab* between the plot area, axis and legend; inside the plot area every
        data point reads out its values.
      - Drill-through: in the Top 10 table, *Shift+F10* → *Drill through* → *Product Detail*. The back button comes
        first on that page and returns with *Ctrl+Enter* (Desktop's Ctrl+click rule; plain *Enter* in the service).
      - Pages: *Ctrl+F6* to the page tabs, then *Tab* or arrow keys and *Enter*.
      - It caught the tab order running backwards on every page (see
        [Tab order counts down](#working-with-the-project-outside-desktop)); fixed before the run above.
      - Known limits, both in Desktop: *Tab* from a focused text box stops on Desktop's editing *More options*
        button (*Shift+Tab* and *Ctrl+F6* still move on, and the text boxes have header icons off for readers),
        and the category tooltip page only opens on hover, so keyboard users get the data point's values instead.
- [x] Phone layouts (*View → Mobile layout*) for the six pages and Product Detail: one column with the filters on
      top, KPI cards in a two-column grid, then the charts. The wide tables and heatmaps (category matrix, cohort
      retention, top 10 products, store list, budget heatmap) are left out on phones. The tooltip page needs none.

## Performance checklist

Measured on the 10M dataset; results and method in [performance.md](performance.md).

- [x] Visuals under 1 s on the 10M dataset: 81 of 87 distinct queries run under 1 s cold and all under 0.9 s warm. The
      six exceptions count distinct customers among 1.7M (1.1 to 1.8 s cold).
- [x] No slicers on high-cardinality columns (customer name, order number). Use search or drill-through instead.
- [x] Prefer measures over visual-level calculations. Avoid `FILTER(ALL(Sales), …)` patterns.
- [x] Model size checked (`tools/PerfKit vertipaq`): 742 MB at 10M, after removing the attribute hierarchies of
      columns that are only aggregated and the unused customer coordinates. `Sales[Order Number]` is the largest
      column (90 MB); it is still needed for `[Orders]` under product filters.

## Working with the project outside Desktop

These are lessons from building this report by editing TMDL/PBIR files directly:

- **Fully restart Power BI Desktop after editing model files.** Reopening the project inside a running
  Desktop session reloads the engine, but the report layer can keep its old field list. New measures then
  evaluate in DAX but are silently dropped from visuals, and measure-driven titles don't render. Close the
  whole app, then open the `.pbip` again.
- **Every model object needs a `lineageTag`.** Desktop adds them on save; hand-written objects don't have
  one. `python scripts/add_lineage_tags.py` adds stable tags, and CI fails if any are missing.
- **Field parameter display columns.** `SELECTEDVALUE('Metric Selector'[Metric])` raises a composite-key error
  because the display column is grouped with the hidden fields column. Read both columns together
  (`SUMMARIZE('Metric Selector', [Metric], [Metric Fields])`), as `[Selected Metric Label]` does.
- **Calculation groups make every measure Variant.** Text measures (labels, dynamic titles) still work, as
  long as calculation items that do arithmetic pass non-numeric values through (the `ISNUMBER` guard in
  *YoY* and *YoY %*).
- **No map visuals.** Azure Maps only renders in a Desktop session that is signed in, so anyone opening
  the `.pbip` without an account sees "sign in" instead of a map. The Bing-based Map and Filled map
  visuals are being retired (Desktop offers to upgrade them to Azure Maps). The Stores & Channels page
  shows geography as a country bar chart with a State drill-down level instead.
- **Tab order counts down.** Power BI moves keyboard focus from the visual with the highest `tabOrder` to the
  lowest, the opposite of what the numbers suggest. Moving the page title one place up in *View → Selection →
  Tab order*, between neighbours at 3000 and 2000, made Desktop save it as 2500. The report first numbered its
  visuals upwards in reading order, so keyboard users went through every page backwards until the keyboard
  walkthrough caught it, and `validate_report.py` now checks the right direction.
- **Report page tooltips.** A visual points at a tooltip page with `visualTooltip` → `show` + `section`
  (the page name), which is what Desktop writes. The `type` values are `Default` and `Canvas`; any other
  value is silently ignored and the plain tooltip shows instead. `validate_report.py` now checks
  container settings like this one against the theme schema, so CI catches it.
- **Phone layouts are one file per visual.** A visual appears on the phone canvas (324 units wide) when it
  has a `mobile.json` next to its `visual.json`: its position there, plus any formatting that differs on
  phones (`objects`, `visualContainerObjects`). KPI cards need `layout.orientation` 0 (grid) with a
  column and row count, because the default keeps every tile in one row that scrolls sideways. Button
  slicer tiles need about 45 units of height: at 37 the bottom of every label was clipped on the phone,
  with or without text wrap. `validate_report.py` checks these overrides like any other formatting.
