# Project Plan — Personal Budget Data Pipeline

## Overview

This project takes a manually-maintained Excel budget workbook — one sheet logging
individual transactions, a second computing actual-vs-planned spend per category via
`SUMIFS` — and rebuilds it as a small but real data platform: a normalized relational
schema, a repeatable ingestion pipeline, versioned SQL transformations, scheduled
orchestration, and a dashboard, with an optional ML layer once the pipeline is stable.

The goal is a portfolio project that demonstrates data engineering fundamentals —
schema design, ingestion, transformation, orchestration, and lineage — end to end,
using a dataset the author actually understands and maintains.

## Architecture decisions

| Decision | Choice | Rationale |
|---|---|---|
| Database engine | PostgreSQL 16 | Real concurrency, first-class dbt/orchestrator support, production-representative experience — free to self-host, no functional trade-off versus a paid engine at this scale. |
| Local dev environment | Docker Compose | Free, reproducible, isolates the project from the host machine, mirrors the production schema exactly. |
| Always-on database | [Neon](https://neon.tech) (free tier, serverless Postgres) | Genuinely internet-reachable 24/7 at $0/month via scale-to-zero — compute suspends after 5 minutes idle and wakes in milliseconds on the next query. No server to patch or pay for. |
| Source data | Manual daily entry (Excel) | >90% of transactions are credit card; the bank's native export only covers chequing cleanly. Ingestion is built source-agnostic so a bank-CSV feed can be added later as a second source, not a redesign. |
| Migration tool | [dbmate](https://github.com/amacneil/dbmate) | Single static binary, database-agnostic, plain versioned SQL (no ORM abstraction to explain), applies identically to local Docker and Neon. |
| Orchestration (Phase 4) | GitHub Actions, scheduled workflow | Free compute, runs without a personal machine powered on, doubles as CI/CD experience on the resume. |
| Amount convention | Signed `NUMERIC(10,2)`, positive = income, negative = expense | Inherited directly from the source workbook — avoids a redundant transaction-type column when the sign already encodes it. |

## Repository structure

```
budget-pipeline/
├── README.md
├── PROJECT_PLAN.md
├── docker-compose.yml
├── .env.example
├── db/
│   ├── migrations/          # versioned schema, dbmate-managed
│   └── seed_categories.sql  # reference data
└── docs/
    ├── phase-1-schema-design.md
    ├── phase-2-ingestion.md      (coming next)
    ├── phase-3-transformation.md
    ├── phase-4-orchestration.md
    ├── phase-5-dashboard.md
    └── phase-6-ml.md
```

## Environment strategy

Two Postgres instances share one migrations directory:

- **`DATABASE_URL`** — local Docker Postgres, for development and testing.
- **`NEON_DATABASE_URL`** — Neon free-tier project, the always-addressable copy used
  by scheduled pipeline runs and any deployed dashboard.

Applying a migration to either is the same command with a different `--url`, which
keeps the two environments provably identical rather than drifting apart.

## Naming conventions (binding for every phase)

- `snake_case` for every table and column.
- Monetary values: `NUMERIC(10,2)`, never `FLOAT` or `REAL`.
- Point-in-time values: `TIMESTAMPTZ`. Calendar dates with no time component: `DATE`.
- Migration filenames: `YYYYMMDDHHMMSS_description.sql` (dbmate default).
- Every foreign key is `ON DELETE RESTRICT` unless a phase doc explicitly says
  otherwise and explains why — silent data loss on a personal finance dataset is
  worse than a blocked delete.

## Phase index

1. **Schema design** — `docs/phase-1-schema-design.md`
2. **Ingestion** — Excel workbook → Postgres, with lineage tracking
3. **Transformation** — dbt models replacing the sheet's `SUMIFS` logic
4. **Orchestration** — scheduled, automated pipeline runs via GitHub Actions
5. **Dashboard** — replaces the `Monthly Budget Summary` sheet
6. **ML (optional)** — auto-categorization or anomaly detection, once the pipeline
   has enough real transaction history to make it worthwhile
