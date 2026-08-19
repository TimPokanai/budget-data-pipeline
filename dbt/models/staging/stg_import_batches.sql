-- One row per ingestion run, source-conformed. Not yet referenced by any
-- mart -- staged now so a future ops/lineage view doesn't need a new
-- staging model, just a new mart reading this one.

with source as (

    select * from {{ source('budget_pipeline', 'import_batches') }}

)

select
    id                as import_batch_id,
    source_file,
    source_type,
    loaded_at,
    row_count,
    status

from source
