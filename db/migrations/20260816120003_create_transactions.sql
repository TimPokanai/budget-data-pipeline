-- migrate:up
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    txn_date DATE NOT NULL,
    description TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    amount NUMERIC(10, 2) NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'td_csv')),
    import_batch_id INTEGER REFERENCES import_batches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_transactions_txn_date ON transactions(txn_date);
CREATE INDEX idx_transactions_category_id ON transactions(category_id);

-- migrate:down
DROP TABLE transactions;
