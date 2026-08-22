"""Generates one corrupted fixture workbook per row-validation rule in
docs/testing-guide.md's Phase 2 regression table ("Row-level validation
still catches bad rows"). Each output is the full base fixture from
fixture_data.py with exactly one transaction row mutated -- so ingesting it
in --dry-run mode should report len(TRANSACTIONS)-1 valid rows and exactly
one rejection, with the specific reason asserted below.

Each case gets its own directory holding a correctly-named
monthly_spreadsheet_Jan_25.xlsx, rather than one directory of
differently-named files, so ingest/parser.py's real filename-based
budget-month derivation is exercised unchanged -- no --budget-month
override needed just to make CI-only filenames parseable.

Usage:
    python scripts/ci/generate_corrupted_fixtures.py [output_dir]

scripts/ci/check_corrupted_fixtures.sh drives these against
`ingest.cli --dry-run` and asserts the expected_reason_contains string
below actually appears in that row's rejection.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from fixture_data import BUDGET_MONTH_NUM, BUDGET_YEAR, FILENAME, TRANSACTIONS, mutate
from generate_fixture_workbook import build_workbook

# Row index -> (case directory name, mutated row list, substring expected in
# validator.py's rejection reason for that row). Indices are into the base
# TRANSACTIONS list in fixture_data.py -- see that file's comments for what
# each row is.
_NEXT_MONTH = 2 if BUDGET_MONTH_NUM == 1 else BUDGET_MONTH_NUM + 1
_NEXT_MONTH_YEAR = BUDGET_YEAR if BUDGET_MONTH_NUM != 12 else BUDGET_YEAR + 1

CASES = {
    "unrecognized_category": {
        # row 2: "Gas station", Transportation, -55.20
        "transactions": lambda: mutate(2, category="NotACategory"),
        "expected_reason_contains": "unrecognized category 'NotACategory'",
    },
    "expense_amount_flipped_positive": {
        # row 4: "Grocery run", Groceries, -142.37
        "transactions": lambda: mutate(4, amount=142.37),
        "expected_reason_contains": "is expense-type but amount is positive",
    },
    "income_amount_flipped_negative": {
        # row 0: "Paycheck", Income, +2600.00
        "transactions": lambda: mutate(0, amount=-2600.00),
        "expected_reason_contains": "is income-type but amount is negative",
    },
    "blank_description": {
        # row 5: "Grocery run", Groceries, -118.02
        "transactions": lambda: mutate(5, description=None),
        "expected_reason_contains": "empty description",
    },
    "date_outside_budget_month": {
        # row 6: "Grocery run", Groceries, -136.90 -- pushed into February
        "transactions": lambda: mutate(
            6, date_override=date(_NEXT_MONTH_YEAR, _NEXT_MONTH, 5)
        ),
        "expected_reason_contains": "not the workbook's budget month",
    },
}


def default_output_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "tests" / "fixtures" / "corrupted"


def generate_all(output_dir: Path) -> None:
    for case_name, case in CASES.items():
        case_dir = output_dir / case_name
        out_path = case_dir / FILENAME
        build_workbook(out_path, transactions=case["transactions"]())
        print(f"Wrote corrupted fixture [{case_name}]: {out_path}")

    # Sanity check at generation time, not just at CI-test time: every case
    # must differ from the base dataset in exactly one row, or a future
    # edit to fixture_data.py silently broke the "N-1/N valid" invariant
    # every case relies on.
    for case_name, case in CASES.items():
        mutated = case["transactions"]()
        diffs = sum(1 for a, b in zip(TRANSACTIONS, mutated) if a != b)
        assert diffs == 1, (
            f"case {case_name!r} mutates {diffs} rows, expected exactly 1 -- "
            f"fixture_data.TRANSACTIONS may have changed shape underneath it"
        )


if __name__ == "__main__":
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else default_output_dir()
    generate_all(out_dir)
