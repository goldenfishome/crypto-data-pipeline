-- Override dbt's default schema naming so models land in exact schema names
-- (staging, intermediate, marts) instead of dev_staging, dev_intermediate, etc.
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
