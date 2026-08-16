# Personal Budget Data Pipeline

A personal monthly budget, originally tracked by hand in Excel, rebuilt as a proper
data pipeline: normalized Postgres schema → automated ingestion → dbt transforms →
scheduled orchestration → dashboard.

**Stack:** PostgreSQL · Docker · Python · dbt · GitHub Actions · Neon (serverless Postgres)

## Why this exists

The original workbook (`Expense Tracker` + `Categories` + `Monthly Budget Summary`,
linked with `SUMIFS`) worked fine for tracking spend by hand, but it's a dead end for
automation, history, and analysis. This project keeps the same manual-entry workflow —
still the fastest way to log a $4 coffee — while rebuilding everything downstream of it
as real infrastructure.

## Project phases


| Phase | Focus                          | Doc                                                              |
| ----- | ------------------------------ | ---------------------------------------------------------------- |
| 1     | Schema design                  | `[docs/phase-1-schema-design.md](docs/phase-1-schema-design.md)` |
| 2     | Ingestion (Excel → Postgres)   | `[docs/phase-2-ingestion.md](docs/phase-2-ingestion.md)`         |
| 3     | Transformation (dbt)           | `docs/phase-3-transformation.md`                                 |
| 4     | Orchestration (GitHub Actions) | `docs/phase-4-orchestration.md`                                  |
| 5     | Dashboard                      | `docs/phase-5-dashboard.md`                                      |




Full architecture decisions and conventions live in `[PROJECT_PLAN.md](PROJECT_PLAN.md)`.

## Quickstart (Phase 1 — schema only, so far)

```bash
# 1. Start local Postgres
docker compose up -d

# 2. Copy env template and fill in values
cp .env.example .env

# 3. Install dbmate (migration tool) if you don't have it
brew install dbmate   # or see https://github.com/amacneil/dbmate#installation

# 4. Run migrations against local Postgres
dbmate --url "$DATABASE_URL" up

# 5. Load reference category data
psql "$DATABASE_URL" -f db/seed_categories.sql
```

To point the same migrations at your free-tier Neon project instead, run step 4 with
`NEON_DATABASE_URL` in place of `DATABASE_URL`.
