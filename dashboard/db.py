"""Database connection for the Phase 5 dashboard.

Uses Streamlit's built-in SQL connection (`st.connection(..., type="sql")`),
which wraps SQLAlchemy and reads connection details straight out of
dashboard/.streamlit/secrets.toml -- see secrets.toml.example for the
local/neon split this mirrors from dbt/profiles.yml.example.

Every query in queries.py goes through get_connection() below, which is the
only thing in this app that knows how to reach Postgres -- and it only ever
reaches it as `budget_dashboard`, the read-only role created by
db/grant_dashboard_readonly.sql. There is no code path in this app that
writes to the database; the role itself enforces that at the Postgres
level, not just by convention here. See docs/phase-5-dashboard.md.
"""

from __future__ import annotations

import streamlit as st


def get_connection():
    """Returns the SQL connection for whichever target secrets.toml's
    top-level `target` key names (`local` or `neon`) -- same target
    vocabulary as --env/--target/--url elsewhere in this project, kept in
    the secrets file since that's the config surface Streamlit itself
    reads, with no CLI flag once this is deployed."""
    target = st.secrets.get("target", "local")
    return st.connection(target, type="sql")
