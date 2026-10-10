{% docs __overview__ %}
# Contoso Retail Analytics: dbt project

The transformation layer of [Contoso Retail Analytics](https://github.com/leon2378/powerbi-contoso-retail-analytics),
an end-to-end Power BI project. dbt and DuckDB turn SQLBI's Contoso V2 Parquet release into the star schema that the
Power BI semantic model imports.

- **Staging** (`models/staging`): one view per source file (sales, customer, product, store) that renames, casts and
  minimises PII.
- **Marts** (`models/marts`): `fct_sales`, `fct_sales_budget`, four dimensions and the RLS entitlements in
  `security_user_access`. Every mart has an enforced contract and is exported to Parquet, which Power BI reads
  locally and `publish_to_onelake.py` loads into a Fabric Lakehouse as Delta tables.
- **Seeds**: budget growth targets and RLS entitlements.
- **Tests**: data tests, unit tests, a source ↔ mart reconciliation test and a check on the order-grain assumption
  behind the fast `[Orders]` measure.

Use the button at the bottom right of any page to open the lineage graph. It ends at the Power BI report, declared as
an exposure (`contoso_retail_power_bi_report`), so you can see which marts the report depends on.

GitHub Actions rebuilds this site whenever the dbt project changes on `main`. It is built on the synthetic fixture
data that CI uses, which has the same schema as the SQLBI release, so the models, columns, tests and lineage match
the real build.
{% enddocs %}
