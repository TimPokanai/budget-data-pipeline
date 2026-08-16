-- migrate:up
-- dedup_key is generated so re-ingesting an edited workbook can skip rows
-- already loaded (ON CONFLICT DO NOTHING) without the writer computing the key.
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    txn_date DATE NOT NULL,
    description TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    amount NUMERIC(10, 2) NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'td_csv')),
    import_batch_id INTEGER REFERENCES import_batches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- date::text is STABLE (depends on DateStyle), so generated columns
    -- cannot use it. Year/month/day extracts are IMMUTABLE.
    dedup_key TEXT GENERATED ALWAYS AS (
        md5(
            (EXTRACT(YEAR FROM txn_date)::integer)::text || '-' ||
            lpad((EXTRACT(MONTH FROM txn_date)::integer)::text, 2, '0') || '-' ||
            lpad((EXTRACT(DAY FROM txn_date)::integer)::text, 2, '0') || '|' ||
            description || '|' ||
            category_id::text || '|' ||
            amount::text || '|' ||
            source
        )
    ) STORED
);

CREATE INDEX idx_transactions_txn_date ON transactions(txn_date);
CREATE INDEX idx_transactions_category_id ON transactions(category_id);
CREATE UNIQUE INDEX transactions_dedup_key_key ON transactions (dedup_key);

-- migrate:down
DROP TABLE transactions;
