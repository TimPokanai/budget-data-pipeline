"""Row-level validation.

Phase 1 deliberately left "amount sign matches category type" out of the
database (no trigger), pushing it here instead, where a bad row can be
rejected with a specific, actionable error before it ever reaches Postgres.
That's the main job of this module; the rest of the checks (unknown
category, blank description, out-of-month date) exist for the same reason.

`categories` is a {name: "income" | "expense"} map. In production it's read
from the `categories` table (the authoritative source). When no database
connection is available -- e.g. `--dry-run` with no DATABASE_URL set --
`default_category_types()` below reconstructs it from the single rule
documented in phase-1-schema-design.md: "Income" is the only income-type
category, everything else is expense-type. If a category is ever added that
breaks that rule, the seed data and this fallback both need updating
together -- `seed_categories.sql` is the source of truth either way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

TOTAL_ROW_LABEL = "Total"


def default_category_types(category_names: list[str]) -> dict[str, str]:
    """Fallback category->type map for offline/dry-run use. See module
    docstring -- this must stay consistent with seed_categories.sql."""
    return {name: ("income" if name == "Income" else "expense") for name in category_names}


@dataclass
class RowError:
    row_index: int
    reasons: list[str]

    def __str__(self) -> str:
        return f"row {self.row_index}: {'; '.join(self.reasons)}"


@dataclass
class ValidationResult:
    valid: pd.DataFrame
    errors: list[RowError] = field(default_factory=list)
    excluded: int = 0  # rows intentionally skipped (not errors) -- see validate_budgets

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_transactions(
    df: pd.DataFrame,
    categories: dict[str, str],
    budget_month: date,
) -> ValidationResult:
    errors: list[RowError] = []
    keep = []

    for idx, row in df.iterrows():
        reasons = []

        category = str(row["Category"]).strip() if pd.notna(row["Category"]) else ""
        description = str(row["Description"]).strip() if pd.notna(row["Description"]) else ""
        amount = row["Amount (CAD)"]
        txn_date = row["Date"]

        if not description:
            reasons.append("empty description")

        if category not in categories:
            reasons.append(f"unrecognized category {category!r} (not in categories dimension)")
        elif pd.notna(amount):
            cat_type = categories[category]
            if cat_type == "income" and amount < 0:
                reasons.append(f"category {category!r} is income-type but amount is negative ({amount})")
            elif cat_type == "expense" and amount > 0:
                reasons.append(f"category {category!r} is expense-type but amount is positive ({amount})")

        if pd.isna(amount):
            reasons.append("missing amount")

        if pd.isna(txn_date):
            reasons.append("missing date")
        else:
            row_month = date(txn_date.year, txn_date.month, 1)
            if row_month != budget_month:
                reasons.append(
                    f"date {txn_date.date()} falls in {row_month.isoformat()[:7]}, "
                    f"not the workbook's budget month {budget_month.isoformat()[:7]}"
                )

        if reasons:
            errors.append(RowError(row_index=idx, reasons=reasons))
        else:
            keep.append(idx)

    return ValidationResult(valid=df.loc[keep].copy(), errors=errors)


def validate_budgets(
    df: pd.DataFrame,
    categories: dict[str, str],
) -> ValidationResult:
    """Validates the `Monthly Budget Summary` sheet's Planned column, which
    feeds the `budgets` table. The Total row is dropped, not an error --
    it's a derived aggregate the sheet keeps for human eyes, not a category.
    Counted separately as `excluded` so callers can report "N/N category
    rows valid" instead of a misleading "N/(N+1)" that reads like a failure."""
    errors: list[RowError] = []
    keep = []
    excluded = 0

    for idx, row in df.iterrows():
        category = str(row["Category"]).strip() if pd.notna(row["Category"]) else ""
        if category == TOTAL_ROW_LABEL:
            excluded += 1
            continue

        reasons = []
        planned = row["Planned (CAD)"]

        if category not in categories:
            reasons.append(f"unrecognized category {category!r} (not in categories dimension)")
        if pd.isna(planned):
            reasons.append("missing planned amount")

        if reasons:
            errors.append(RowError(row_index=idx, reasons=reasons))
        else:
            keep.append(idx)

    return ValidationResult(valid=df.loc[keep].copy(), errors=errors, excluded=excluded)
