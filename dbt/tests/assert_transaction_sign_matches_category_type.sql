-- Singular test: fails (returns rows) if any transaction's amount sign
-- doesn't match its category's type.
--
-- ingest/validator.py already enforces this at write time (see
-- docs/phase-1-schema-design.md's "no DB trigger" decision, and
-- docs/phase-2-ingestion.md) -- this is a second, independent check at
-- the transform layer. It exists to catch a row that reached
-- `transactions` some other way (a manual psql INSERT, a future non-Python
-- loader) and never passed through the ingest validator, not to duplicate
-- what the CLI already guarantees for its own writes.

select
    t.transaction_id,
    t.category_name,
    t.category_type,
    t.amount
from {{ ref('fct_transactions') }} t
where
    (t.category_type = 'income'  and t.amount < 0)
    or (t.category_type = 'expense' and t.amount > 0)
