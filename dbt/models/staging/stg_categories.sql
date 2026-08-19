-- One row per category, source-conformed: renamed to stg_ conventions,
-- no joins, no aggregation. See docs/phase-3-transformation.md.

with source as (

    select * from {{ source('budget_pipeline', 'categories') }}

)

select
    id            as category_id,
    name          as category_name,
    type          as category_type,
    created_at    as category_created_at

from source
