-- migrate:up
CREATE TABLE import_batches (
    id SERIAL PRIMARY KEY,
    source_file TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'excel_manual',
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_count INTEGER,
    status TEXT NOT NULL DEFAULT 'success' CHECK (status IN ('success', 'partial', 'failed'))
);

-- migrate:down
DROP TABLE import_batches;
