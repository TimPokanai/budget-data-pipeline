-- One row per (category, month) plan, source-conformed.

with source as (

    select * from {{ source('budget_pipeline', 'budgets') }}

)

select
    id                as budget_id,
    category_id,
    budget_month,
    planned_amount

from source
