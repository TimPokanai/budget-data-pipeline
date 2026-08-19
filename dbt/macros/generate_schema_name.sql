{#
    dbt's default generate_schema_name macro appends a model's custom
    +schema config onto the connection's target schema, e.g. a `+schema:
    staging` model lands in `public_staging` rather than `staging`. That's
    the right default for a shared warehouse with many dbt projects in one
    database, but this project has one target schema (`public`, from the
    Phase 1 migrations) and wants `staging`/`marts` to exist as themselves
    -- so a future dashboard (Phase 5) or an ad hoc psql session finds
    tables exactly where docs/phase-3-transformation.md says they are.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
