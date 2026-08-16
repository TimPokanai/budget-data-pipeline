-- migrate:up
CREATE TABLE budgets (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    budget_month DATE NOT NULL,
    planned_amount NUMERIC(10, 2) NOT NULL,
    CONSTRAINT budgets_month_is_first_of_month CHECK (EXTRACT(DAY FROM budget_month) = 1),
    CONSTRAINT budgets_unique_category_month UNIQUE (category_id, budget_month)
);

CREATE INDEX idx_budgets_month ON budgets(budget_month);

-- migrate:down
DROP TABLE budgets;
