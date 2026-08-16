"""Postgres load functions.

Idempotency note: `transactions` has no natural key in the Phase 1 schema --
only a surrogate `id`. Because the source workbook is edited throughout the
month rather than written once, re-running ingestion against the same
(growing) file is the normal case, not an edge case. Migration
20260816140000_add_transaction_dedup_key.sql adds a generated, deterministic
`dedup_key` column + unique index specifically so this module can express
that as `ON CONFLICT (dedup_key) DO NOTHING` instead of hand-rolled
diffing. See docs/phase-2-ingestion.md for the reasoning.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
import psycopg2
import psycopg2.extras


def get_connection(database_url: str):
    return psycopg2.connect(database_url)


def fetch_categories(conn) -> dict[str, tuple[int, str]]:
    """Returns {category_name: (category_id, type)} -- the authoritative
    dimension data, used to override the offline dry-run fallback whenever
    a live connection is available."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, type FROM categories")
        return {name: (cat_id, cat_type) for cat_id, name, cat_type in cur.fetchall()}


def insert_import_batch(conn, source_file: str, source_type: str = "excel_manual") -> int:
    """Inserts a placeholder batch row up front (status='partial') so that
    even a run which later fails outright still leaves an audit trail --
    finalize_batch() updates it once the outcome is known."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO import_batches (source_file, source_type, loaded_at, row_count, status)
            VALUES (%s, %s, %s, 0, 'partial')
            RETURNING id
            """,
            (source_file, source_type, datetime.now(timezone.utc)),
        )
        batch_id = cur.fetchone()[0]
    conn.commit()
    return batch_id


def finalize_batch(conn, batch_id: int, row_count: int, status: str) -> None:
    assert status in {"success", "partial", "failed"}
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE import_batches SET row_count = %s, status = %s WHERE id = %s",
            (row_count, status, batch_id),
        )
    conn.commit()


def upsert_transactions(
    conn,
    df: pd.DataFrame,
    categories: dict[str, tuple[int, str]],
    batch_id: int,
    source: str = "manual",
) -> int:
    """Bulk-inserts validated transaction rows. Rows whose dedup_key already
    exists are silently skipped (they were loaded by an earlier run of this
    same, since-edited file) -- returns the number of *new* rows actually
    inserted, which may be less than len(df)."""
    if df.empty:
        return 0

    rows = [
        (
            row["Date"].date() if hasattr(row["Date"], "date") else row["Date"],
            str(row["Description"]).strip(),
            categories[str(row["Category"]).strip()][0],
            row["Amount (CAD)"],
            source,
            batch_id,
        )
        for _, row in df.iterrows()
    ]

    with conn.cursor() as cur:
        result = psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO transactions
                (txn_date, description, category_id, amount, source, import_batch_id)
            VALUES %s
            ON CONFLICT (dedup_key) DO NOTHING
            RETURNING id
            """,
            rows,
            fetch=True,
        )
        inserted = len(result)
    conn.commit()
    return inserted


def upsert_budgets(
    conn,
    df: pd.DataFrame,
    categories: dict[str, tuple[int, str]],
    budget_month: date,
) -> int:
    """Upserts planned amounts. Unlike transactions, budgets DO get
    overwritten on conflict -- the Planned column is the one thing in the
    source workbook that's expected to be edited in place across re-runs
    within the same month."""
    if df.empty:
        return 0

    rows = [
        (
            categories[str(row["Category"]).strip()][0],
            budget_month,
            row["Planned (CAD)"],
        )
        for _, row in df.iterrows()
    ]

    with conn.cursor() as cur:
        result = psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO budgets (category_id, budget_month, planned_amount)
            VALUES %s
            ON CONFLICT (category_id, budget_month)
            DO UPDATE SET planned_amount = EXCLUDED.planned_amount
            RETURNING id
            """,
            rows,
            fetch=True,
        )
        affected = len(result)
    conn.commit()
    return affected
