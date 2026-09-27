{#
    Post-hook for mart models: writes the freshly built table to
    <CONTOSO_MARTS_DIR>/<model>.parquet. Power BI (local mode) reads these files, and
    scripts/publish_to_onelake.py pushes the same files to the Fabric Lakehouse as Delta tables.
    The directory must exist before dbt runs (tasks.ps1 / CI create it).
#}
{% macro export_to_parquet() %}
    {%- set marts_dir = env_var('CONTOSO_MARTS_DIR', 'data/marts') | replace('\\', '/') -%}
    copy (select * from {{ this }})
    to '{{ marts_dir }}/{{ this.identifier }}.parquet'
    (format parquet, compression zstd, row_group_size 1000000)
{% endmacro %}
