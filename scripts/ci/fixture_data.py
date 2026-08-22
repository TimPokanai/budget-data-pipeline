"""Canonical synthetic dataset for the Phase 4 CI fixture workbook.

Kept separate from generate_fixture_workbook.py so generate_corrupted_fixtures.py
can import and mutate the *same* base dataset a corrupted fixture is built
from, instead of hand-duplicating rows in two places that could quietly
drift apart.

January 2025 is used as the fixture month deliberately: it's fully in the
past, so it never collides with a real month someone is actively tracking,
and it's fixed (not "last month") so CI output doesn't shift over time.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

BUDGET_YEAR = 2025
BUDGET_MONTH_NUM = 1  # January
FILENAME = "monthly_spreadsheet_Jan_25.xlsx"  # must match parser.FILENAME_PATTERN


@dataclass(frozen=True)
class Txn:
    day: int
    description: str | None
    category: str
    amount: float
    # Bypasses date(BUDGET_YEAR, BUDGET_MONTH_NUM, day) entirely when set --
    # used by generate_corrupted_fixtures.py to construct the
    # out-of-budget-month case without a second dataset shape.
    date_override: date | None = None

    @property
    def txn_date(self) -> date:
        return self.date_override or date(BUDGET_YEAR, BUDGET_MONTH_NUM, self.day)


# Matches db/seed_categories.sql exactly -- order matters only for the
# Categories sheet's dropdown list, not for validation.
CATEGORY_NAMES = [
    "Income", "Transportation", "Groceries", "Eating Out", "Subscriptions",
    "Fees", "Brenna", "Entertainment", "Treats", "Savings", "Investments",
    "Emergency Fund", "Miscellaneous",
]

# Signed amounts, same convention as the real workbook: positive = income,
# negative = expense. Covers every category at least once.
TRANSACTIONS: list[Txn] = [
    Txn(1, "Paycheck", "Income", 2600.00),
    Txn(15, "Paycheck", "Income", 2600.00),
    Txn(2, "Gas station", "Transportation", -55.20),
    Txn(9, "Monthly transit pass", "Transportation", -99.00),
    Txn(3, "Grocery run", "Groceries", -142.37),
    Txn(10, "Grocery run", "Groceries", -118.02),
    Txn(17, "Grocery run", "Groceries", -136.90),
    Txn(24, "Grocery run", "Groceries", -104.55),
    Txn(5, "Dinner out", "Eating Out", -64.10),
    Txn(12, "Coffee shop", "Eating Out", -8.75),
    Txn(19, "Takeout", "Eating Out", -31.40),
    Txn(1, "Streaming service", "Subscriptions", -15.99),
    Txn(1, "Cloud storage", "Subscriptions", -2.99),
    Txn(6, "Bank fee", "Fees", -4.50),
    Txn(13, "Gift for Brenna", "Brenna", -45.00),
    Txn(27, "Dinner with Brenna", "Brenna", -62.30),
    Txn(8, "Movie tickets", "Entertainment", -28.00),
    Txn(22, "Concert ticket", "Entertainment", -85.00),
    Txn(11, "Ice cream", "Treats", -9.50),
    Txn(25, "Bakery", "Treats", -14.25),
    Txn(1, "Transfer to savings", "Savings", -300.00),
    Txn(15, "Transfer to savings", "Savings", -300.00),
    Txn(5, "Index fund contribution", "Investments", -250.00),
    Txn(20, "Emergency fund top-up", "Emergency Fund", -100.00),
    Txn(18, "Miscellaneous purchase", "Miscellaneous", -22.10),
]

# One row per real category (13) -- no Total row here, that's a derived
# aggregate added at write time, matching the real workbook.
BUDGETS: list[tuple[str, float]] = [
    ("Income", 5200.00),
    ("Transportation", 180.00),
    ("Groceries", 550.00),
    ("Eating Out", 150.00),
    ("Subscriptions", 25.00),
    ("Fees", 10.00),
    ("Brenna", 120.00),
    ("Entertainment", 100.00),
    ("Treats", 30.00),
    ("Savings", 600.00),
    ("Investments", 250.00),
    ("Emergency Fund", 100.00),
    ("Miscellaneous", 50.00),
]


def mutate(index: int, **overrides) -> list[Txn]:
    """Returns a copy of TRANSACTIONS with a single row replaced.

    Used by generate_corrupted_fixtures.py -- each corrupted fixture changes
    exactly one field on exactly one row, so ingesting it should report
    len(TRANSACTIONS)-1 valid rows with one specific rejection reason.
    """
    rows = list(TRANSACTIONS)
    rows[index] = replace(rows[index], **overrides)
    return rows
