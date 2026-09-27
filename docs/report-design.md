# Report design guide

The report is 1280 × 720, built on a 16 px grid, with the **Contoso Executive** theme
(`StaticResources/RegisteredResources/ContosoExecutive.json`). The first page, **Executive Overview**, is
already built. The pages below are the plan for the rest of the report.

## Page plan

| Page | Question it answers | Suggested visuals | Model features it shows off |
|---|---|---|---|
| **Executive Overview** ✅ | How are we doing vs last year and vs budget? | KPI cards, sales vs budget trend, category YoY matrix, country bars | Time Intelligence calc group, grain-aware budget |
| **Sales Performance** | What drives revenue? | Line chart driven by the **Metric Selector** field parameter; small multiples by channel; decomposition tree (Category → Subcategory → Brand) | Field parameter, calc group in a slicer |
| **Customers** | Are we acquiring and keeping customers? | New vs returning (stacked columns by month), cohort matrix (*Acquisition Cohort* × *Year*, value *Customers*), age band × gender | `New Customers`, cohort attribute |
| **Products** | What sells, at what price and margin? | Scatter of Sales Amount vs Margin % per subcategory, price-band mix, top-N products table | Price bands, margin measures |
| **Stores & Channels** | Where do we sell? | Map by store country (bubble size = Sales Amount), online vs physical trend, store table with open/close dates | Store hierarchy, RLS (test with *View as*) |
| **Budget Variance** | Where are we off plan? | Waterfall of *Sales vs Budget* by category, matrix month × category with conditional formatting on *Sales vs Budget %* | Many-to-many budget relationships |
| **Product detail** (drill-through) | Everything about one product | Card row, monthly trend, customer age mix | Drill-through filters |
| **Tooltip page** | Context on hover | Mini trend + margin for the hovered category | Report page tooltips |

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

- [ ] Every visual has alt text (*Format → General → Alt text*). Use a dynamic measure for KPI cards.
- [ ] Tab order follows reading order (*View → Selection → Tab order*).
- [ ] Information is never carried by colour alone (labels, icons, patterns).
- [ ] Text contrast ≥ 4.5:1. The theme's ink colours `#0B0B0B` and `#52514E` pass on white.
- [ ] Keyboard-only walkthrough of every page, including slicers and drill-through.
- [ ] Mobile layout for the Executive Overview (*View → Mobile layout*).

## Performance checklist

- [ ] Performance Analyzer: every visual under 1 s on the 10M dataset.
- [ ] No slicers on high-cardinality columns (customer name, order number). Use search or drill-through instead.
- [ ] Prefer measures over visual-level calculations. Avoid `FILTER(ALL(Sales), …)` patterns.
- [ ] Check the model size with VertiPaq Analyzer (DAX Studio). `Sales[Order Number]` is the largest column; keep it
      only while drill-to-order is needed.
