#!/usr/bin/env bash
# Constraint regression check -- docs/testing-guide.md, Phase 1 test #2.
#
# Runs each deliberately-bad statement from the testing guide's table
# against $DATABASE_URL and confirms it is REJECTED. If any of these
# succeeds, that's the regression -- a constraint that used to protect the
# data no longer does, most likely from an edited migration.
#
# Expects: migrations applied, categories seeded (13 rows, 'Income' first
# per db/seed_categories.sql's insert order) -- true right after the CI
# workflow's "Apply migrations" + "Seed categories" steps, before anything
# has ingested transactions yet.
set -uo pipefail

: "${DATABASE_URL:?DATABASE_URL must be set}"
FAIL=0

# Runs a statement that is expected to be REJECTED by a constraint.
# Passes if psql exits non-zero; fails (loudly) if psql exits 0.
expect_rejected() {
  local label="$1"
  local sql="$2"
  if psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "$sql" >/tmp/check_constraints_out 2>&1; then
    echo "FAIL [$label]: statement succeeded but should have been rejected"
    echo "  SQL: $sql"
    FAIL=1
  else
    echo "PASS [$label]: rejected as expected"
  fi
}

# Look up Income's id rather than assuming 1 -- true on a freshly-seeded
# database (SERIAL starts at 1, Income is seed_categories.sql's first row)
# but resolving it explicitly is one less assumption to keep in sync.
INCOME_ID="$(psql "$DATABASE_URL" -tAc "SELECT id FROM categories WHERE name = 'Income'")"
if [[ -z "$INCOME_ID" ]]; then
  echo "FAIL: could not find an 'Income' category -- was db/seed_categories.sql run?"
  exit 1
fi

expect_rejected "categories CHECK on type" \
  "INSERT INTO categories (name, type) VALUES ('CI Test Category', 'bogus');"

expect_rejected "categories UNIQUE on name" \
  "INSERT INTO categories (name, type) VALUES ('Income', 'income');"

expect_rejected "budgets CHECK day-is-1" \
  "INSERT INTO budgets (category_id, budget_month, planned_amount) VALUES ($INCOME_ID, '2026-08-15', 100);"

# Unique-violation case needs one successful insert first, then the
# duplicate -- the duplicate is the one actually asserted against.
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c \
  "INSERT INTO budgets (category_id, budget_month, planned_amount) VALUES ($INCOME_ID, '2027-01-01', 100);" \
  >/dev/null 2>&1
expect_rejected "budgets UNIQUE on (category_id, budget_month)" \
  "INSERT INTO budgets (category_id, budget_month, planned_amount) VALUES ($INCOME_ID, '2027-01-01', 200);"
psql "$DATABASE_URL" -c "DELETE FROM budgets WHERE category_id = $INCOME_ID AND budget_month = '2027-01-01';" >/dev/null 2>&1

expect_rejected "transactions FK on category_id" \
  "INSERT INTO transactions (txn_date, description, category_id, amount) VALUES ('2026-08-01', 'CI test row', 9999, 100);"

# RESTRICT case needs a category that actually has a transaction. Insert
# one against Income, then try to delete Income itself.
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c \
  "INSERT INTO transactions (txn_date, description, category_id, amount) VALUES ('2026-08-01', 'CI restrict-check row', $INCOME_ID, 1);" \
  >/dev/null 2>&1
expect_rejected "categories FK RESTRICT (category has transactions)" \
  "DELETE FROM categories WHERE id = $INCOME_ID;"
psql "$DATABASE_URL" -c "DELETE FROM transactions WHERE description = 'CI restrict-check row';" >/dev/null 2>&1

if [[ $FAIL -ne 0 ]]; then
  echo
  echo "One or more constraint checks failed -- see FAIL lines above."
  exit 1
fi

echo
echo "All constraint checks passed."
