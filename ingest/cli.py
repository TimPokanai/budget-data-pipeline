"""Entrypoint: `python -m ingest.cli --file path/to/workbook.xlsx [options]`

Orchestrates the pipeline described in docs/phase-2-ingestion.md:
read workbook -> validate rows -> (report only, or load to Postgres).
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from . import loader
from .config import load_config
from .parser import WorkbookError, read_workbook
from .validator import default_category_types, validate_budgets, validate_transactions

log = logging.getLogger("ingest")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Ingest a monthly budget workbook into Postgres.")
    p.add_argument("--file", required=True, type=Path, help="Path to the .xlsx workbook")
    p.add_argument(
        "--env", choices=["local", "neon"], default="local",
        help="Which Postgres target to load into (default: local)",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Parse and validate only -- print what would be loaded, touch no database. "
             "Runs fully offline; DB connection is only used opportunistically for the "
             "authoritative category list, and falls back to the documented sign-convention "
             "rule if unavailable.",
    )
    p.add_argument(
        "--allow-partial", action="store_true",
        help="Load valid rows even if some rows fail validation (batch status='partial'). "
             "Default is strict: any row error aborts the whole batch.",
    )
    p.add_argument(
        "--budget-month", type=str, default=None,
        help="Override the budget month (YYYY-MM-01) instead of deriving it from the filename.",
    )
    return p


def _resolve_budget_month_override(raw: str | None) -> date | None:
    if raw is None:
        return None
    return date.fromisoformat(raw)


def run(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)

    try:
        workbook = read_workbook(args.file, _resolve_budget_month_override(args.budget_month))
    except WorkbookError as e:
        log.error("Failed to read workbook: %s", e)
        return 1

    log.info("Parsed %s -- budget month %s", workbook.source_file, workbook.budget_month.isoformat()[:7])

    # Always attempt a connection, even on --dry-run: it's the only way to get
    # authoritative category IDs/types rather than the offline fallback rule.
    conn = None
    categories: dict[str, tuple[int, str]] | None = None
    try:
        config = load_config(args.env)
        conn = loader.get_connection(config.database_url)
        categories = loader.fetch_categories(conn)
        log.info("Connected to %s Postgres; loaded %d categories", args.env, len(categories))
    except Exception as e:  # noqa: BLE001 -- deliberately broad: any connection problem falls back
        if args.dry_run:
            log.warning("No database connection available (%s) -- falling back to the "
                        "documented sign-convention rule for category types.", e)
            categories = None
        else:
            log.error("Could not connect to the %s database: %s", args.env, e)
            return 1

    category_types = (
        {name: t for name, (_, t) in categories.items()} if categories
        else default_category_types(workbook.category_names)
    )

    txn_result = validate_transactions(workbook.transactions, category_types, workbook.budget_month)
    budget_result = validate_budgets(workbook.budget_summary, category_types)

    for err in txn_result.errors:
        log.warning("[transactions] %s", err)
    for err in budget_result.errors:
        log.warning("[budgets] %s", err)

    budget_category_rows = len(workbook.budget_summary) - budget_result.excluded
    log.info(
        "Validation: %d/%d transaction rows valid, %d/%d budget category rows valid "
        "(%d non-category row(s) excluded, e.g. 'Total')",
        len(txn_result.valid), len(workbook.transactions),
        len(budget_result.valid), budget_category_rows,
        budget_result.excluded,
    )

    has_errors = not (txn_result.ok and budget_result.ok)
    if has_errors and not args.allow_partial and not args.dry_run:
        log.error("Row validation errors present and --allow-partial not set -- aborting, nothing loaded.")
        return 1

    if args.dry_run:
        log.info("Dry run complete -- no database writes performed.")
        return 0 if (txn_result.ok and budget_result.ok) else 2

    assert conn is not None and categories is not None
    batch_id = loader.insert_import_batch(conn, workbook.source_file)
    try:
        inserted = loader.upsert_transactions(conn, txn_result.valid, categories, batch_id)
        budgeted = loader.upsert_budgets(conn, budget_result.valid, categories, workbook.budget_month)
        status = "success" if not has_errors else "partial"
        loader.finalize_batch(conn, batch_id, inserted, status)
        log.info(
            "Loaded batch %d: %d new transactions inserted (%d already present), "
            "%d budget rows upserted -- status=%s",
            batch_id, inserted, len(txn_result.valid) - inserted, budgeted, status,
        )
    except Exception:
        loader.finalize_batch(conn, batch_id, 0, "failed")
        raise
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(run())
