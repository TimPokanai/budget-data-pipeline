# Personal Budget Data Pipeline

[CI](https://github.com/TimPokanai/budget-pipeline/actions/workflows/ci.yml)

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


| Phase | Focus                          | Doc                                                                |
| ----- | ------------------------------ | ------------------------------------------------------------------ |
| 1     | Schema design                  | `[docs/phase-1-schema-design.md](docs/phase-1-schema-design.md)`   |
| 2     | Ingestion (Excel → Postgres)   | `[docs/phase-2-ingestion.md](docs/phase-2-ingestion.md)`           |
| 3     | Transformation (dbt)           | `[docs/phase-3-transformation.md](docs/phase-3-transformation.md)` |
| 4     | Orchestration (GitHub Actions) | `[docs/phase-4-orchestration.md](docs/phase-4-orchestration.md)`   |
| 5     | Dashboard                      | `docs/phase-5-dashboard.md`                                        |


Full architecture decisions and conventions live in `[PROJECT_PLAN.md](PROJECT_PLAN.md)`.

## Local development setup (macOS)

A from-scratch walkthrough for a Mac with none of this installed yet. Already have a
tool below? Skip that step. This brings you from a bare machine to a working copy of
everything built through Phase 3 (schema + ingestion + transformation).

**1. Install Homebrew**, if you don't have it:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the installer's own instructions for adding `brew` to your `PATH` — they differ
for Apple Silicon vs. Intel Macs.

**2. Install Docker Desktop**, and actually start it:

```bash
brew install --cask docker
```

Open **Docker.app** from `/Applications` once so it finishes first-run setup and starts
the Docker daemon. `docker compose` (below) fails silently otherwise — check for the
whale icon in the menu bar before moving on.

**3. Install Miniconda, dbmate, and psql**:

```bash
brew install --cask miniconda
brew install dbmate libpq
brew link --force libpq   # puts `psql` on your PATH; libpq is keg-only by default

conda init zsh   # or `bash`, matching your shell -- restart your terminal after this
```

Miniconda manages the Python environment (used below instead of `venv`); `dbmate`
applies everything in `db/migrations/`; `psql` is used below for seeding and one-off
queries.

**4. Clone the repo and set up a conda environment**:

```bash
git clone <repo-url> budget-pipeline
cd budget-pipeline

conda create -n budget-pipeline python=3.12 -y
conda activate budget-pipeline
pip install -r requirements.txt
```

`requirements.txt` is installed via `pip` inside the conda env rather than
`conda install` package-by-package — simpler, and it's what's already pinned. Any new
terminal session needs `conda activate budget-pipeline` again before running the
ingestion script below.

**5. Configure environment variables**:

```bash
cp .env.example .env
```

Open `.env` and fill in:

- `POSTGRES_PASSWORD` — any password for local dev; `docker-compose.yml` reads this
directly to initialize the container.
- `DATABASE_URL` — must embed that **same password**. User and database name are fixed
by `docker-compose.yml` (`budget_admin` / `budget_pipeline`), so only the password
and host/port are yours to set.
- `NEON_DATABASE_URL` — can stay a placeholder until you're actually pointing at Neon.
- `NEON_PGHOST` / `NEON_PGUSER` / `NEON_PGPASSWORD` / `NEON_PGDATABASE` — only needed
once you're running dbt against Neon (step 9 below); dbt-postgres wants these as
discrete fields rather than the single `NEON_DATABASE_URL` string. Can also stay
placeholders until then.

**Load** `.env` **into your shell.** Creating the file above doesn't make these
variables available to commands — Docker Compose reads `.env` automatically for its
own substitution, but `dbmate`, `psql`, and the ingestion script all expect real shell
environment variables, which nothing does for you automatically:

```bash
set -a
source .env
set +a

echo "$DATABASE_URL"   # sanity check -- should print the URL, not blank
```

Do this in every new terminal session before running the commands below (or use
`[direnv](https://direnv.net/)` to automate it per-directory). If a command downstream
fails with something like `connection to server on socket "/tmp/.s.PGSQL.5432" failed`,
that's `$DATABASE_URL` being empty — come back and re-run this.

**6. Start local Postgres**:

```bash
docker compose up -d
docker compose ps   # confirm it's Up before continuing
```

First run pulls the `postgres:16` image, so it can take a minute.

**7. Apply migrations and seed reference data**:

```bash
dbmate --url "$DATABASE_URL" up
psql "$DATABASE_URL" -f db/seed_categories.sql
```

`dbmate up` applies every file in `db/migrations/` in order — this now includes Phase
2's `dedup_key` migration on top of Phase 1's four tables.

**8. Verify the ingestion pipeline end-to-end**:

```bash
# Dry-run against a real workbook -- validates without touching the DB
python -m ingest.cli --file monthly_spreadsheet_Aug_26.xlsx --dry-run

# Actually load it
python -m ingest.cli --file monthly_spreadsheet_Aug_26.xlsx --env local
```

A `status=success` log line means local setup is done. Spot-check it:

```bash
psql "$DATABASE_URL" -c "SELECT * FROM import_batches ORDER BY id DESC LIMIT 1;"
```

**9. Install dbt and build the transformation layer** (Phase 3):

```bash
cd dbt
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
dbt deps
```

dbt's dependencies live in their own virtualenv here rather than the
`budget-pipeline` conda env used above — dbt-core pins a lot of its own transitive
dependencies, and keeping it isolated avoids a version fight with the ingestion
script's pins. `dbt deps` installs `dbt_utils`, used by a couple of the schema tests.

Configure dbt's connection:

```bash
cp profiles.yml.example profiles.yml
```

Fill in the `local` target — it reuses the same `budget_admin` user and reads
`POSTGRES_PASSWORD` from the `.env` you already sourced in step 5, so there's nothing
new to fill in there. `profiles.yml` is gitignored, same as `.env` at the repo root —
never commit it.

Build and test everything:

```bash
dbt debug --target local   # sanity-check the connection before building anything
dbt build --target local
```

`dbt build` runs every model in dependency order and then every test — look for every
model and test to report `OK`/`PASS`, with 0 errors. dbt creates the `staging` and
`marts` schemas itself on first run, which needs the connecting role to have `CREATE`
on the database (true by default for `budget_admin`).

Spot-check it the same way step 8 spot-checked ingestion:

```bash
psql "$DATABASE_URL" -c "SELECT * FROM marts.fct_budget_actuals ORDER BY budget_month, category_name;"
```

`deactivate` this venv and `conda activate budget-pipeline` again before going back to
the ingestion script in a fresh terminal — the two environments are kept separate on
purpose (see above).

**(Optional) Point the same migrations, ingestion, and dbt build at Neon**:

```bash
dbmate --url "$NEON_DATABASE_URL" up
psql "$NEON_DATABASE_URL" -f db/seed_categories.sql
python -m ingest.cli --file monthly_spreadsheet_Aug_26.xlsx --env neon

# dbt against the same Neon project -- needs NEON_PGHOST/NEON_PGUSER/NEON_PGPASSWORD/
# NEON_PGDATABASE filled in from step 5 (dbt-postgres takes discrete connection
# fields, not the single NEON_DATABASE_URL string dbmate/psycopg2 use)
cd dbt && dbt build --target neon
```



## Continuous integration & orchestration (Phase 4)

Two GitHub Actions workflows live in `.github/workflows/`:

- `ci.yml` — runs the full Phases 1–3 regression suite from
`docs/testing-guide.md` on every push and PR, against a throwaway Postgres
service container and a synthetic fixture workbook (`scripts/ci/`). No setup
required — it works on a fresh clone/fork with zero secrets.
- `scheduled-refresh.yml` — runs daily against the real Neon database:
rebuilds every dbt mart and runs `dbt source freshness`, so a stalled pipeline
fails loudly instead of silently. Needs four repository secrets
(`NEON_PGHOST`, `NEON_PGUSER`, `NEON_PGPASSWORD`, `NEON_PGDATABASE` — the same
values already in your local `.env`) added under **Settings → Secrets and
variables → Actions**.

Real ingestion (`python -m ingest.cli --env neon`) stays a manual, local step after
editing the workbook — see
`[docs/phase-4-orchestration.md](docs/phase-4-orchestration.md)` for why, and for
the full design rationale behind both workflows.

## Docker command reference

Everyday commands for the local Postgres container (`docker-compose.yml` names the
service `postgres`, the container `budget_pipeline_db`).


| Task                                          | Command                                                                                                                               |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Start Postgres in the background              | `docker compose up -d`                                                                                                                |
| Stop Postgres, keep data                      | `docker compose down`                                                                                                                 |
| Stop Postgres, **wipe all data**              | `docker compose down -v`                                                                                                              |
| Check container status                        | `docker compose ps`                                                                                                                   |
| Tail Postgres logs                            | `docker compose logs -f postgres`                                                                                                     |
| Restart just Postgres                         | `docker compose restart postgres`                                                                                                     |
| Open a `psql` shell inside the container      | `docker exec -it budget_pipeline_db psql -U budget_admin -d budget_pipeline`                                                          |
| Run a SQL file against the container directly | `docker exec -i budget_pipeline_db psql -U budget_admin -d budget_pipeline < path/to/file.sql`                                        |
| Inspect the data volume                       | `docker volume inspect budget-pipeline_pgdata`                                                                                        |
| Live resource usage (CPU/mem)                 | `docker stats budget_pipeline_db`                                                                                                     |
| Full reset — fresh DB from scratch            | `docker compose down -v && docker compose up -d && dbmate --url "$DATABASE_URL" up && psql "$DATABASE_URL" -f db/seed_categories.sql` |


A few things worth knowing before using these:

- `docker compose down -v` deletes the `pgdata` volume — every transaction and budget
row goes with it. Handy when local state has drifted from what you're testing;
never point the `-v` flag at Neon, since there's no volume to delete there and
it's not what this command targets anyway.
- `budget_pipeline_db` is fixed by `docker-compose.yml`'s `container_name`, so these
commands work regardless of what you name the Compose project or service.
- The volume name follows Compose's `<project-dir>_<volume-key>` convention. If your
local clone isn't in a directory named `budget-pipeline`, run `docker volume ls`
first to get the actual name before using `docker volume inspect` directly.

