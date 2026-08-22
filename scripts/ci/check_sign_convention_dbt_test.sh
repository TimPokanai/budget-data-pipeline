#!/usr/bin/env bash
# Defense-in-depth regression -- docs/testing-guide.md, Phase 3 test #3.
#
# ingest/validator.py enforces the amount-sign-matches-category-type rule
# at write time, but dbt/tests/assert_transaction_sign_matches_category_type.sql
# is a second, independent check for rows that reach `transactions` some
# other way (manual psql INSERT, a future non-Python loader). This script
# proves that second check isn't just theater: it deliberately bypasses
# ingest/validator.py with a direct INSERT, confirms the dbt test fails and
# names the bad row, cleans up, then confirms it passes again.
#
# Expects: migrations applied, categories seeded, dbt deps already run, cwd
# irrelevant (paths below are absolute from the repo root).
set -uo pipefail

: "${DATABASE_URL:?DATABASE_URL must be set}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DBT_TARGET="${DBT_TARGET:-local}"
MARKER="ci sign-convention regression row"

cleanup() {
  psql "$DATABASE_URL" -c "DELETE FROM transactions WHERE description = '$MARKER';" >/dev/null 2>&1
}
trap cleanup EXIT

INCOME_ID="$(psql "$DATABASE_URL" -tAc "SELECT id FROM categories WHERE name = 'Income'")"
if [[ -z "$INCOME_ID" ]]; then
  echo "FAIL: could not find an 'Income' category -- was db/seed_categories.sql run?"
  exit 1
fi

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c \
  "INSERT INTO transactions (txn_date, description, category_id, amount) VALUES ('2025-01-01', '$MARKER', $INCOME_ID, -50.00);" \
  >/dev/null

cd "$REPO_ROOT/dbt"

echo "--- Building with the bad row present (expect the singular test to FAIL) ---"
if dbt build --target "$DBT_TARGET" --select fct_transactions assert_transaction_sign_matches_category_type; then
  echo "FAIL: dbt build succeeded, but assert_transaction_sign_matches_category_type should have failed on the bad row"
  exit 1
fi
echo "PASS: singular test failed as expected while the bad row was present"

cleanup
trap - EXIT

echo "--- Rebuilding after cleanup (expect a clean pass) ---"
if ! dbt build --target "$DBT_TARGET" --select fct_transactions assert_transaction_sign_matches_category_type; then
  echo "FAIL: dbt build still failing after the bad row was removed"
  exit 1
fi
echo "PASS: singular test passes again after cleanup"
