"""Postgres-backed durability for agent state.

Two things live here, both built on a single connection pool sized to your
Render Postgres plan:

* ``make_pool()`` — an ``AsyncConnectionPool`` configured for psycopg3 +
  LangGraph (autocommit, dict rows, no server-side prepared statements).
* ``make_checkpointer(pool)`` — an ``AsyncPostgresSaver`` so LangGraph persists
  every step of the agent run. State survives process restarts and is shared
  across replicas, which is what makes human-in-the-loop resume work.

The same pool is reused by ``db/reports.py`` so the whole app respects one
connection budget (see R4: pooling sized to the plan).
"""

from __future__ import annotations

import os

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/deepagents"


def get_database_url() -> str:
    """Return a psycopg3-compatible connection string.

    Render hands out ``postgres://`` URLs; psycopg expects ``postgresql://``.
    """
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    return url


def _pool_size() -> tuple[int, int]:
    """Resolve (min_size, max_size) for the pool.

    Size ``DB_POOL_MAX_SIZE`` to your Render Postgres plan's connection limit,
    divided across the number of running instances (web + each Workflow). The
    defaults are deliberately conservative for the free / starter plans.
    """
    max_size = int(os.environ.get("DB_POOL_MAX_SIZE", "10"))
    min_size = int(os.environ.get("DB_POOL_MIN_SIZE", "1"))
    return min(min_size, max_size), max_size


def make_pool() -> AsyncConnectionPool:
    """Create (but do not open) a connection pool for the checkpointer + app.

    Call ``await pool.open()`` once at startup and ``await pool.close()`` on
    shutdown — the FastAPI lifespan in ``api/app.py`` does this for you.
    """
    min_size, max_size = _pool_size()
    return AsyncConnectionPool(
        conninfo=get_database_url(),
        min_size=min_size,
        max_size=max_size,
        open=False,
        # psycopg3 settings required by the LangGraph Postgres checkpointer.
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            "prepare_threshold": 0,
        },
    )


async def make_checkpointer(pool: AsyncConnectionPool) -> AsyncPostgresSaver:
    """Build the checkpointer over an *already-open* pool and ensure its tables.

    ``setup()`` is idempotent; it creates the checkpoint tables on first run.
    """
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()
    return checkpointer
