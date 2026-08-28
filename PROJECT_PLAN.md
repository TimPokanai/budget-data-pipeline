# Project Plan — Personal Budget Data Pipeline

## Overview

This project takes a manually-maintained Excel budget workbook — one sheet logging
individual transactions, a second computing actual-vs-planned spend per category via
`SUMIFS` — and rebuilds it as a small but real data platform: a normalized relational
schema, a repeatable ingestion pipeline, versioned SQL transformations, scheduled
orchestration, and a dashboard, with an optional ML layer once the pipeline is stable.

## Architecture decisions


| Decision                | Choice                                                        | Rationale                                                                                                                                                                                                 |
| ----------------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Database engine         | PostgreSQL 16                                                 | Real concurrency, first-class dbt/orchestrator support, production-representative experience — free to self-host, no functional trade-off versus a paid engine at this scale.                             |
| Local dev environment   | Docker Compose                                                | Free, reproducible, isolates the project from the host machine, mirrors the production schema exactly.                                                                                                    |
| Always-on database      | [Neon](https://neon.tech) (free tier, serverless Postgres)    | Genuinely internet-reachable 24/7 at $0/month via scale-to-zero — compute suspends after 5 minutes idle and wakes in milliseconds on the next query. No server to patch or pay for.                       |
| Source data             | Manual daily entry (Excel)                                    | >90% of transactions are credit card; the bank's native export only covers chequing cleanly. Ingestion is built source-agnostic so a bank-CSV feed can be added later as a second source, not a redesign. |
| Migration tool          | [dbmate](https://github.com/amacneil/dbmate)                  | Single static binary, database-agnostic, plain versioned SQL (no ORM abstraction to explain), applies identically to local Docker and Neon.                                                               |
| Transformation tool     | [dbt](https://www.getdbt.com) (`dbt-postgres` adapter)        | Versioned, tested SQL models instead of the workbook's `SUMIFS`/`Difference` formulas; same local/Neon split as everything else, via `--target`.                                                          |
| Orchestration (Phase 4) | GitHub Actions, scheduled workflow                            | Free compute, runs without a personal machine powered on, doubles as CI/CD experience on the resume.                                                                                                      |
| Dashboard tool (Phase 5) | [Streamlit](https://streamlit.io), on Streamlit Community Cloud | Free tier, and a real Python application (connection handling, caching, multi-page routing) rather than point-and-click BI config. Same language as the Phase 2 ingestion CLI. See `docs/phase-5-dashboard.md`.|
| Dashboard DB access (Phase 5) | Dedicated `budget_dashboard` role, `SELECT`-only on `marts`, direct to Neon — no API layer | Postgres enforces the read-only boundary itself rather than trusting application code; an API layer would be a second free-tier service to host and secure for a problem a database role already solves. |
| Amount convention       | Signed `NUMERIC(10,2)`, positive = income, negative = expense | Inherited directly from the source workbook — avoids a redundant transaction-type column when the sign already encodes it.                                                                                |




## Repository structure

```
budget-pipeline/
├── .github/
│   └── workflows/
│       ├── ci.yml                  # push/PR regression suite, ephemeral Postgres
│       └── scheduled-refresh.yml   # daily dbt build + source freshness, Neon
├── dashboard/
│   ├── streamlit_app.py      # Home page -- budget overview
│   ├── db.py                 # get_connection() -- reads secrets.toml's `target`
│   ├── queries.py             # every SQL query the app runs, all against marts.*
│   ├── requirements.txt
│   ├── README.md
│   ├── pages/
│   │   ├── 1_Transactions.py
│   │   └── 2_Trends.py
│   └── .streamlit/
│       └── secrets.toml.example   # copy to secrets.toml, gitignored
├── db/
│   ├── migrations/          # versioned schema, dbmate-managed
│   ├── seed_categories.sql  # reference data
│   └── grant_dashboard_readonly.sql  # creates + grants the budget_dashboard role
├── dbt/
│   ├── dbt_project.yml
│   ├── packages.yml         # dbt_utils
│   ├── profiles.yml.example # copy to profiles.yml, gitignored
│   ├── requirements.txt
│   ├── macros/
│   ├── models/
│   │   ├── staging/         # stg_* -- 1:1 renamed views over raw tables
│   │   └── marts/           # dim_*/fct_* -- what everything else reads
│   └── tests/                # singular (non-schema) tests
├── docs/
│   ├── phase-1-schema-design.md
│   ├── phase-2-ingestion.md
│   ├── phase-3-transformation.md
│   ├── phase-4-orchestration.md
│   ├── phase-5-dashboard.md     # this phase
│   ├── phase-6-ml.md
│   └── testing-guide.md
├── ingest/
│   ├── cli.py
│   ├── config.py
│   ├── loader.py
│   ├── parser.py
│   └── validator.py
├── scripts/
│   └── ci/                          # Phase 4 -- fixture generation + regression scripts
│       ├── fixture_data.py
│       ├── generate_fixture_workbook.py
│       ├── generate_corrupted_fixtures.py
│       ├── check_constraints.sh
│       ├── check_corrupted_fixtures.sh
│       └── check_sign_convention_dbt_test.sh
├── tests/
│   └── fixtures/                    # generated at CI runtime, gitignored -- not committed
│       └── corrupted/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── LICENSE
├── PROJECT_PLAN.md
└── README.md
```



## Environment strategy

Two Postgres instances share one migrations directory, and now one dbt project:

- `DATABASE_URL` — local Docker Postgres, for development and testing.
- `NEON_DATABASE_URL` — Neon free-tier project, the always-addressable copy used
by scheduled pipeline runs and any deployed dashboard.

Applying a migration to either is the same command with a different `--url`, running
ingestion against either is the same command with a different `--env`, and building
dbt models against either is the same command with a different `--target` — three
tools, one local/Neon split, kept deliberately uniform rather than each inventing its
own flag name.

## Naming conventions (binding for every phase)

- `snake_case` for every table and column.
- Monetary values: `NUMERIC(10,2)`, never `FLOAT` or `REAL`.
- Point-in-time values: `TIMESTAMPTZ`. Calendar dates with no time component: `DATE`.
- Migration filenames: `YYYYMMDDHHMMSS_description.sql` (dbmate default).
- Every foreign key is `ON DELETE RESTRICT` unless a phase doc explicitly says
otherwise and explains why — silent data loss on a personal finance dataset is
worse than a blocked delete.
- dbt staging models: `stg_<source_table>`, 1:1 grain, renaming/casting only.
  dbt marts: `dim_<entity>` / `fct_<entity>`. See `docs/phase-3-transformation.md`.
- Postgres roles: `budget_<purpose>` — `budget_admin` (full access, the app/pipeline
  user) and `budget_dashboard` (read-only, `marts` schema only). See
  `docs/phase-5-dashboard.md`.



## Phase index

1. **Schema design** — `docs/` contains design documents for each phase
2. **Ingestion** — Excel workbook → Postgres, with lineage tracking
3. **Transformation** — dbt models replacing the sheet's `SUMIFS` logic
4. **Orchestration** — scheduled, automated pipeline runs via GitHub Actions
5. **Dashboard** — replaces the `Monthly Budget Summary` sheet
6. **Looking beyond...** - what's coming next
