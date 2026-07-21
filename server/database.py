"""Async SQLite engine + schema init (architecture.md §3, §5.1).

All durable state lives in SQLite behind the Repository. This module builds the async engine
(`sqlite+aiosqlite`), turns on FK enforcement per-connection, and creates the schema. Tests bind a
throwaway engine (a temp-file DB) via `create_engine`/`create_session_maker`, so `./arena.db` is
never touched under test.
"""

from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

# Config-driven default. SQLite `*.db` files are gitignored; delete the file to reset all matches.
DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./arena.db"


class Base(DeclarativeBase):
    """Declarative base for the four ORM tables (server/models.py)."""


def create_engine(url: str = DEFAULT_DATABASE_URL) -> AsyncEngine:
    """Build an async engine with FK enforcement on every connection.

    NullPool (no connection reuse) keeps many short-lived test engines over temp-FILE DBs from
    stepping on each other. NOTE: NullPool is unsafe with `:memory:` (each new connection gets a
    fresh empty DB), so tests use temp files, not `:memory:`.
    """
    engine = create_async_engine(url, poolclass=NullPool)

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_session_maker(engine: AsyncEngine) -> async_sessionmaker[Any]:
    """A session factory; `expire_on_commit=False` so ORM objects stay usable after commit."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_models(engine: AsyncEngine) -> None:
    """Create all four tables in the bound database (idempotent — `create_all` skips existing)."""
    # Import here so the models register on Base.metadata before create_all runs.
    from server import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Process-wide defaults for `uvicorn server.main:app`; tests override with a throwaway engine.
engine: AsyncEngine = create_engine()
async_session_maker: async_sessionmaker[Any] = create_session_maker(engine)
