# CI fixtures

This directory holds the synthetic workbook `scripts/ci/generate_fixture_workbook.py`
generates, plus the corrupted variants `scripts/ci/generate_corrupted_fixtures.py`
generates under `corrupted/`. Neither script's output is committed — `.gitignore`'s
blanket `*.xlsx` rule (which exists to keep the real, personal monthly workbook out
of the repo) covers these too, on purpose, so there's one rule instead of an
exception carved out for "these particular xlsx files are fine."

To recreate what CI generates, from the repo root:

```bash
cd scripts/ci
python generate_fixture_workbook.py
python generate_corrupted_fixtures.py
```

See `[docs/phase-4-orchestration.md](../../docs/phase-4-orchestration.md)` for what
each file contains and why.
