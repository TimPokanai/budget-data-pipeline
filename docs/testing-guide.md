# Testing Guide — Regression & End-to-End (Phases 1–3)

This doc covers two different kinds of testing, and it's worth keeping them separate:

- **Regression tests** confirm that something which already worked still works after a
change — a new migration, an edited dbt model, a tweak to `validator.py`. Each check
below maps back to a behavior a phase doc already established as correct.
- **End-to-end tests** confirm the *whole* pipeline works, start to finish, on a clean
environment — from an empty database to a queryable `fct_budget_actuals` table that
matches the source workbook.

Run regression tests after any change to `db/`, `ingest/`, or `dbt/`. Run the
end-to-end test after any change to the environment itself (new machine, rebuilt
Docker volume, new Neon project) or before treating a release as "done."

## Prerequisites

- [ ] `docker compose up -d` running, or a reachable Neon project
- [ ] `.env` filled in at the repo root (copied from `.env.example`)
- [ ] `dbt/profiles.yml` filled in (copied from `dbt/profiles.yml.example`)
- [ ] `pip install -r requirements.txt` (root) and `pip install -r dbt/requirements.txt`
  ```
  (inside `dbt/`, ideally its own venv — see `dbt/README.md`)
  ```
- [ ] `dbt deps` run at least once (installs `dbt_utils`)
- [ ] A known-good monthly workbook to test against — `monthly_spreadsheet_Aug_26.xlsx`
  ```
  is the one already verified in `docs/phase-2-ingestion.md` (50/50 transaction
  rows valid, 13/13 real budget categories), so it's a good default fixture
  ```

---



## Regression tests



### Phase 1 — Schema

**1. Migrations apply and roll back cleanly**

```bash
dbmate --url "$DATABASE_URL" up
dbmate --url "$DATABASE_URL" down    # x4, one per migration file
dbmate --url "$DATABASE_URL" up
```

Expected: no errors in either direction; `\dt` in `psql` shows all four tables after
the final `up`.

**2. Constraints still reject what they should.** Run each of these against
`$DATABASE_URL` and confirm it fails with the noted error class — if any of these
*succeeds*, that's the regression:


| Attempt                                                                                          | Expected result                                       |
| ------------------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| `INSERT INTO categories (name, type) VALUES ('Test', 'bogus');`                                  | `CHECK` violation on `type`                           |
| `INSERT INTO categories (name, type) VALUES ('Income', 'income');`                               | `UNIQUE` violation on `name`                          |
| `INSERT INTO budgets (category_id, budget_month, planned_amount) VALUES (1, '2026-08-15', 100);` | `CHECK` violation — day isn't 1                       |
| Insert the same `(category_id, budget_month)` into `budgets` twice                               | `UNIQUE` violation on `budgets_unique_category_month` |
| `INSERT INTO transactions (...) VALUES (..., category_id = 9999, ...);`                          | FK violation — no such category                       |
| `DELETE FROM categories WHERE id = 1;` (a category with transactions)                            | FK `RESTRICT` violation, not a silent cascade         |




### Phase 2 — Ingestion

**1. Offline dry-run fallback still works.** Temporarily unset `DATABASE_URL`:

```bash
unset DATABASE_URL
python -m ingest.cli --file monthly_spreadsheet_Aug_26.xlsx --dry-run
```

Expected: a `WARNING` about no DB connection, then validation still completes using
the offline category-type fallback rule.

**2. Row-level validation still catches bad rows.** Using deliberately corrupted
copies of the fixture file (same approach as `docs/phase-2-ingestion.md`'s original
verification):


| Corruption                                    | Expected rejection reason                                       |
| --------------------------------------------- | --------------------------------------------------------------- |
| Category changed to a made-up string          | `unrecognized category '...' (not in categories dimension)`     |
| An expense row's amount flipped positive      | `category '...' is expense-type but amount is positive (...)`   |
| An income row's amount flipped negative       | `category 'Income' is income-type but amount is negative (...)` |
| `Description` blanked on a row                | `empty description`                                             |
| A transaction date moved to a different month | `date ... falls in ..., not the workbook's budget month ...`    |


**3. Idempotent re-ingestion.** Ingest the same file twice in a row:

```bash
python -m ingest.cli --file monthly_spreadsheet_Aug_26.xlsx --env local
python -m ingest.cli --file monthly_spreadsheet_Aug_26.xlsx --env local
```

Expected: the second run logs `0 new transactions inserted (50 already present)` (or
whatever the true row count is) — not 50 new rows, not an error.

**4. Strict mode vs.** `--allow-partial`**.** Using a copy with one corrupted row:

```bash
python -m ingest.cli --file corrupted_copy.xlsx --env local              # strict
python -m ingest.cli --file corrupted_copy.xlsx --env local --allow-partial
```

Expected: the strict run exits 1 and loads nothing (`SELECT count(*) FROM import_batches` unchanged); the `--allow-partial` run loads the valid rows, and its
`import_batches` row has `status = 'partial'`.

**5. Budgets overwrite, transactions don't.** Ingest a file, change one `Planned (CAD)` value in the sheet, re-ingest:

```bash
python -m ingest.cli --file edited_planned_amount.xlsx --env local
```

Expected: `budgets.planned_amount` for that category/month reflects the *new* value
(no duplicate row — `UNIQUE (category_id, budget_month)` plus `DO UPDATE` means one
row, updated), while `transactions` gained zero new rows for anything unchanged.

### Phase 3 — Transformation

**1. Clean build and test.**

```bash
cd dbt && dbt build --target local
```

Expected: every model builds, every test passes, 0 failures.

**2. Idempotent rebuild.** Run `dbt build --target local` a second time with no
underlying data change. Expected: identical row counts and values in every mart —
`fct_budget_actuals` in particular, since it's a `full-refresh` table recomputed from
scratch each run, not incrementally maintained.

**3. Sign-convention test actually fires (defense-in-depth check).** This one
deliberately bypasses `ingest/validator.py` to prove the dbt-layer test isn't just
theater:

```sql
-- Insert a row that violates the sign convention directly, skipping ingest entirely
INSERT INTO transactions (txn_date, description, category_id, amount, source)
VALUES ('2026-08-01', 'regression test row', 1, -50.00, 'manual');  -- category 1 = Income
```

```bash
dbt build --target local --select fct_transactions assert_transaction_sign_matches_category_type
```

Expected: `assert_transaction_sign_matches_category_type` **fails** and returns the
bad row. Then clean up:

```sql
DELETE FROM transactions WHERE description = 'regression test row';
```

and re-run `dbt build` to confirm it passes again.

**4.** `fct_budget_actuals` **uniqueness test.** Under normal operation this should
never fail — Phase 1's `budgets_unique_category_month` constraint already prevents
the underlying duplicate at the source. Treat a failure here as a signal that the
`full outer join` in `fct_budget_actuals.sql` itself has a bug, not that the data is
bad; there's no safe way to manufacture a failing case without editing the model, so
this one is monitored rather than actively poked at.

**5. Source freshness.**

```bash
dbt source freshness --target local
```

Expected: `transactions` reports `pass` if ingested within the last 45 days, `warn`
between 45–90, `error` beyond 90 — confirm the state matches when you actually last
ingested.

### Cross-environment

**1. Local/Neon parity.** Run the full Phase 2 + Phase 3 sequence against `--env neon`
/ `--target neon` with the same fixture file used locally, then compare:

```sql
-- run against both databases, diff the output
SELECT category_name, budget_month, planned_amount, actual_amount, difference_amount
FROM marts.fct_budget_actuals
ORDER BY budget_month, category_name;
```

Expected: identical results on both. Any difference means the two databases have
drifted — check migration status (`dbmate status --url ...`) on both first.

---



## End-to-end test

Run this on a genuinely clean environment (fresh clone, `docker compose down -v`, or
a brand-new Neon project) to confirm the whole pipeline works for someone who's never
touched it before — not just that your existing setup still limps along.

1. **Wipe and restart local Postgres.**
  ```bash
   docker compose down -v
   docker compose up -d
  ```
2. **Configure environment.**
  ```bash
   cp .env.example .env   # fill in real values
  ```
3. **Apply migrations.**
  ```bash
   dbmate --url "$DATABASE_URL" up
  ```
   Expected: all four tables exist, zero rows.
4. **Seed categories.**
  ```bash
   psql "$DATABASE_URL" -f db/seed_categories.sql
  ```
   Expected: `SELECT count(*) FROM categories;` → 13.
5. **Dry-run the fixture workbook first.**
  ```bash
   python -m ingest.cli --file monthly_spreadsheet_Aug_26.xlsx --dry-run
  ```
   Expected: `50/50 transaction rows valid, 13/14 budget rows valid` (14th is the
   dropped `Total` row) — matches `docs/phase-2-ingestion.md`'s original verification
   exactly, confirming nothing has drifted since.
6. **Ingest for real.**
  ```bash
   python -m ingest.cli --file monthly_spreadsheet_Aug_26.xlsx --env local
  ```
   Expected: exit code 0, `import_batches` row with `status = 'success'` and
   `row_count = 50`.
7. **Confirm raw counts.**
  ```sql
   SELECT count(*) FROM transactions;   -- expect 50
   SELECT count(*) FROM budgets;        -- expect 13
   SELECT count(*) FROM import_batches; -- expect 1
  ```
8. **Build the dbt layer.**
  ```bash
   cd dbt
   dbt deps
   dbt build --target local
  ```
   Expected: all 7 models build, all tests pass.
9. **Reproduce Phase 1's manual verification query.**
  ```sql
   SELECT c.name AS category, SUM(t.amount) AS actual
   FROM transactions t JOIN categories c ON c.id = t.category_id
   WHERE date_trunc('month', t.txn_date) = '2026-08-01'
   GROUP BY c.name ORDER BY c.name;
  ```
10. **Query the Phase 3 mart for the same month.**
  ```sql
    SELECT category_name, planned_amount, actual_amount, difference_amount
    FROM marts.fct_budget_actuals
    WHERE budget_month = '2026-08-01'
    ORDER BY category_name;
  ```
    Expected: `actual_amount` in step 10 matches `actual` in step 9, category-for-
    category, exactly.
11. **Compare against the source workbook by eye.** Open
  `monthly_spreadsheet_Aug_26.xlsx`'s `Monthly Budget Summary` sheet and confirm
    `Planned`, `Actual`, and `Difference` match step 10's output for every category.
12. **Re-run the idempotency check end-to-end.**
  ```bash
    python -m ingest.cli --file monthly_spreadsheet_Aug_26.xlsx --env local
    cd dbt && dbt build --target local
  ```
    Expected: step 7's counts are unchanged, and step 10's query returns the same
    values as before.
13. *(Optional but recommended before calling a release "done")* Repeat steps 1–12
  against `--env neon` / `--target neon`.

---



## Pass/fail summary


| Check                     | Pass condition                                                         |
| ------------------------- | ---------------------------------------------------------------------- |
| Migrations                | Apply and roll back with no errors                                     |
| Constraints               | Every listed bad insert is rejected                                    |
| Ingestion validation      | Every corrupted-file case is rejected with the right reason            |
| Idempotent ingestion      | Second run inserts 0 new transactions                                  |
| `--allow-partial`         | Strict aborts with nothing written; partial loads valid rows only      |
| Budget upsert             | Edited `Planned` value overwrites in place, no duplicate row           |
| `dbt build`               | 0 model errors, 0 test failures                                        |
| Idempotent dbt build      | Second run produces identical mart contents                            |
| Sign-convention dbt test  | Fires on a manually-inserted bad row, clears after cleanup             |
| Local/Neon parity         | `fct_budget_actuals` identical across both targets                     |
| End-to-end reconciliation | Phase 1 query, Phase 3 mart, and the source workbook all agree exactly |




## What this doesn't cover

Phases 4 (orchestration) and 5 (dashboard) don't exist yet, so there's nothing here
about scheduled runs, GitHub Actions failures, or a UI layer — this guide only tests
what Phases 1–3 actually built. Extend it once those phases land rather than
speculating about them now.
