# Dashboard — Phase 5

Full design rationale lives in
[`docs/phase-5-dashboard.md`](../docs/phase-5-dashboard.md); this file is
just the quickstart.

## Prerequisites

The read-only `budget_dashboard` role must exist on whichever
database(s) you're pointing this at — see
`db/grant_dashboard_readonly.sql`'s own header comment, or the Setup
section of `docs/phase-5-dashboard.md`, for the exact command.

## Local development

```bash
cd dashboard

# Separate virtualenv recommended -- see requirements.txt for why.
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Fill in the `local` connection's password -- the one you set when you
# ran db/grant_dashboard_readonly.sql against $DATABASE_URL. Leave
# target = "local".

streamlit run streamlit_app.py
```

Opens at `http://localhost:8501`. The `local` target points at the same
Docker Postgres every other phase already uses, so this only ever shows
data you've already ingested locally.

## Deploying (Streamlit Community Cloud)

1. Push this repo to GitHub — it can stay public. See
   `docs/phase-5-dashboard.md`'s Security section for why that's safe:
   the app's *visibility* is controlled separately from the repo's.
2. On [share.streamlit.io](https://share.streamlit.io), create a new app
   pointing at this repo, branch `main`, main file path
   `dashboard/streamlit_app.py`.
3. In the app's **Settings → Secrets**, paste the contents of
   `.streamlit/secrets.toml.example`, filled in with the `neon`
   connection's real values (the second password from
   `db/grant_dashboard_readonly.sql`'s Setup step), and set
   `target = "neon"`.
4. In the app's **Settings → Sharing**, restrict viewers to your own
   Google account email. **Don't skip this step** — without it, the app
   is publicly viewable to anyone with the URL, defeating the whole point
   of the read-only role and gitignored secrets.

## Pages

| File | Shows |
|---|---|
| `streamlit_app.py` | Budget Overview — planned vs. actual vs. difference for a selected month |
| `pages/1_Transactions.py` | Transaction-level drill-down, filterable by month and category |
| `pages/2_Trends.py` | Multi-month income/expense and per-category trend lines |
