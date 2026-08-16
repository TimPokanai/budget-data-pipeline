"""Environment/connection configuration for the ingestion pipeline.

Mirrors the two-environment strategy from PROJECT_PLAN.md: the same migrations,
and now the same ingestion script, target either the local Docker Postgres
(`DATABASE_URL`) or the always-on Neon instance (`NEON_DATABASE_URL`) based on
a single `--env` flag rather than two code paths.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

ENV_VAR_BY_TARGET = {
    "local": "DATABASE_URL",
    "neon": "NEON_DATABASE_URL",
}


@dataclass(frozen=True)
class Config:
    target: str
    database_url: str


def load_config(target: str) -> Config:
    """Resolve a Postgres connection string for the given target.

    Parameters
    ----------
    target:
        Either ``"local"`` or ``"neon"``, matching the `--env` CLI flag.

    Raises
    ------
    ValueError
        If `target` isn't recognized.
    RuntimeError
        If the corresponding environment variable is unset or empty -- this
        is treated as a hard failure rather than a fallback, since silently
        ingesting against the wrong database is worse than refusing to run.
    """
    if target not in ENV_VAR_BY_TARGET:
        raise ValueError(
            f"Unknown --env {target!r}; expected one of {sorted(ENV_VAR_BY_TARGET)}"
        )
    var_name = ENV_VAR_BY_TARGET[target]
    url = os.environ.get(var_name)
    if not url:
        raise RuntimeError(
            f"{var_name} is not set. Copy .env.example to .env, fill it in, "
            f"and make sure it's loaded (e.g. `export $(cat .env | xargs)` or "
            f"python-dotenv) before running the ingestion script."
        )
    return Config(target=target, database_url=url)
