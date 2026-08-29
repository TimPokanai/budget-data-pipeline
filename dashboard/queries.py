"""Read-only query functions against the `marts` schema.

Every query this app runs lives here, in one module, and every one of them
reads marts.* only -- never staging.* or public.* -- matching the boundary
db/grant_dashboard_readonly.sql enforces at the role level (see
docs/phase-5-dashboard.md's Security section for why both layers exist).

Caching is Streamlit's built-in per-query cache (the `ttl` kwarg on
SQLConnection.query), not a second st.cache_data layer -- see
docs/phase-5-dashboard.md's design decisions for why 5 minutes was chosen
(it sits close to Neon's own scale-to-zero idle window).
"""

from __future__ import annotations

import pandas as pd

from db import get_connection

TTL = "5m"


def available_months() -> list[str]:
    """Every budget_month with a row in fct_budget_actuals, most recent
    first -- drives the month selector on the Overview and Transactions
    pages."""
    conn = get_connection()
    df = conn.query(
        "SELECT DISTINCT budget_month FROM marts.fct_budget_actuals "
        "ORDER BY budget_month DESC",
        ttl=TTL,
    )
    return df["budget_month"].astype(str).tolist()


def budget_actuals_for_month(budget_month: str) -> pd.DataFrame:
    """One row per category for the given month -- the direct replacement
    for the source workbook's Monthly Budget Summary sheet."""
    conn = get_connection()
    return conn.query(
        """
        SELECT category_name, category_type, planned_amount,
               actual_amount, difference_amount
        FROM marts.fct_budget_actuals
        WHERE budget_month = :budget_month
        ORDER BY category_name
        """,
        params={"budget_month": budget_month},
        ttl=TTL,
    )


def budget_actuals_all_months() -> pd.DataFrame:
    """Every (category, month) row -- feeds the Trends page's multi-month
    charts. Small enough (13 categories x however many months exist) to
    pull in full rather than paginating."""
    conn = get_connection()
    return conn.query(
        """
        SELECT category_name, category_type, budget_month,
               planned_amount, actual_amount, difference_amount
        FROM marts.fct_budget_actuals
        ORDER BY budget_month, category_name
        """,
        ttl=TTL,
    )


def transactions_for_month(
    budget_month: str, category_name: str | None = None
) -> pd.DataFrame:
    """Transaction-level drill-down for a month, optionally filtered to one
    category -- feeds the Transactions page's table."""
    conn = get_connection()
    if category_name and category_name != "All categories":
        return conn.query(
            """
            SELECT txn_date, description, category_name, amount
            FROM marts.fct_transactions
            WHERE txn_month = :budget_month AND category_name = :category_name
            ORDER BY txn_date, description
            """,
            params={"budget_month": budget_month, "category_name": category_name},
            ttl=TTL,
        )
    return conn.query(
        """
        SELECT txn_date, description, category_name, amount
        FROM marts.fct_transactions
        WHERE txn_month = :budget_month
        ORDER BY txn_date, description
        """,
        params={"budget_month": budget_month},
        ttl=TTL,
    )


def category_names() -> list[str]:
    """Every category name, for the Transactions page's filter dropdown."""
    conn = get_connection()
    df = conn.query(
        "SELECT category_name FROM marts.dim_categories ORDER BY category_name",
        ttl=TTL,
    )
    return df["category_name"].tolist()
