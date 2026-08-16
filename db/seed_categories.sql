-- Reference data: categories from the original workbook's `Categories` sheet.
-- Safe to re-run: existing names are left untouched.
INSERT INTO categories (name, type) VALUES
    ('Income',          'income'),
    ('Transportation',  'expense'),
    ('Groceries',       'expense'),
    ('Eating Out',      'expense'),
    ('Subscriptions',   'expense'),
    ('Fees',            'expense'),
    ('Brenna',          'expense'),
    ('Entertainment',   'expense'),
    ('Treats',          'expense'),
    ('Savings',         'expense'),
    ('Investments',     'expense'),
    ('Emergency Fund',  'expense'),
    ('Miscellaneous',   'expense')
ON CONFLICT (name) DO NOTHING;
