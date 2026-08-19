-- One row per transaction, denormalized with its category. Replaces the
-- lookup the source workbook did implicitly via the `Category` dropdown
-- on `Expense Tracker`.

with transactions as (

    select * from {{ ref('stg_transactions') }}

),

categories as (

    select * from {{ ref('dim_categories') }}

)

select
    t.transaction_id,
    t.txn_date,
    date_trunc('month', t.txn_date)::date as txn_month,
    t.description,
    t.category_id,
    c.category_name,
    c.category_type,
    t.amount,
    t.ingestion_source,
    t.import_batch_id,
    t.loaded_at

from transactions t
left join categories c
    on c.category_id = t.category_id
