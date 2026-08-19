-- One row per transaction, source-conformed. `source` (the workbook vs.
-- a future bank-CSV feed) is renamed to ingestion_source here to avoid
-- colliding with dbt's own `source()` vocabulary in downstream SQL.

with source as (

    select * from {{ source('budget_pipeline', 'transactions') }}

)

select
    id                as transaction_id,
    txn_date,
    description,
    category_id,
    amount,
    source            as ingestion_source,
    import_batch_id,
    dedup_key,
    created_at        as loaded_at

from source
