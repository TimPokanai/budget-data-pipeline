"""Reads the monthly workbook and derives the month it represents.

The workbook itself never states its own month explicitly -- `Monthly Budget
Summary` is just a category/planned/actual table, no date column. The month
lives only in the filename (`monthly_spreadsheet_Aug_26.xlsx` -> Aug 2026),
so that's the primary signal, cross-checked against the transaction dates
actually present in `Expense Tracker` as a guard against a stale or
mis-copied filename.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

REQUIRED_SHEETS = {"Expense Tracker", "Monthly Budget Summary", "Categories"}

# Matches the real naming convention used by the source file, e.g.
# "monthly_spreadsheet_Aug_26.xlsx".
FILENAME_PATTERN = re.compile(
    r"monthly_spreadsheet_(?P<mon>[A-Za-z]{3})_(?P<yy>\d{2})\.xlsx$",
    re.IGNORECASE,
)

_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class WorkbookError(ValueError):
    """Raised for structural problems with the workbook itself (wrong sheets,
    unparsable filename, month/data mismatch) -- distinct from row-level
    validation errors, which are recoverable per-row."""


@dataclass
class ParsedWorkbook:
    source_file: str
    budget_month: date
    transactions: pd.DataFrame
    budget_summary: pd.DataFrame
    category_names: list[str]


def derive_budget_month(path: Path) -> date:
    """Parse the month a workbook represents from its filename.

    Returns the 1st of the month, matching `budgets.budget_month`'s
    day-forced-to-1 convention from phase-1.
    """
    match = FILENAME_PATTERN.search(path.name)
    if not match:
        raise WorkbookError(
            f"Filename {path.name!r} doesn't match the expected "
            f"'monthly_spreadsheet_<Mon>_<YY>.xlsx' pattern. Pass --budget-month "
            f"explicitly (YYYY-MM-01) to override."
        )
    month = _MONTH_ABBR.get(match.group("mon").lower())
    if month is None:
        raise WorkbookError(f"Unrecognized month abbreviation in {path.name!r}")
    year = 2000 + int(match.group("yy"))
    return date(year, month, 1)


def read_workbook(path: Path, budget_month_override: date | None = None) -> ParsedWorkbook:
    """Load and lightly reshape the three sheets. Does not validate row
    contents -- that's `validator.py`'s job -- but does enforce the
    structural invariants a bad file could violate before any row-level
    logic runs."""
    if not path.exists():
        raise WorkbookError(f"No such file: {path}")

    xl = pd.ExcelFile(path)
    missing = REQUIRED_SHEETS - set(xl.sheet_names)
    if missing:
        raise WorkbookError(
            f"{path.name} is missing expected sheet(s): {sorted(missing)}. "
            f"Found: {xl.sheet_names}"
        )

    budget_month = budget_month_override or derive_budget_month(path)

    transactions = xl.parse("Expense Tracker")
    budget_summary = xl.parse("Monthly Budget Summary")
    categories = xl.parse("Categories")

    expected_txn_cols = {"Date", "Description", "Category", "Amount (CAD)"}
    if not expected_txn_cols.issubset(transactions.columns):
        raise WorkbookError(
            f"'Expense Tracker' columns don't match expectations. "
            f"Expected {sorted(expected_txn_cols)}, found {list(transactions.columns)}"
        )

    expected_summary_cols = {"Category", "Planned (CAD)", "Actual (CAD)", "Difference (CAD)"}
    if not expected_summary_cols.issubset(budget_summary.columns):
        raise WorkbookError(
            f"'Monthly Budget Summary' columns don't match expectations. "
            f"Expected {sorted(expected_summary_cols)}, found {list(budget_summary.columns)}"
        )

    if "Names" not in categories.columns:
        raise WorkbookError("'Categories' sheet is missing its 'Names' column")

    return ParsedWorkbook(
        source_file=path.name,
        budget_month=budget_month,
        transactions=transactions,
        budget_summary=budget_summary,
        category_names=categories["Names"].dropna().astype(str).str.strip().tolist(),
    )
