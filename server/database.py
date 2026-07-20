"""Async SQLite persistence — engine, session maker, FK enforcement, and schema init.

All durable state lives in SQLite (architecture.md §3): the engine is async SQLAlchemy over
``sqlite+aiosqlite``, the session maker uses ``expire_on_commit=False`` (ORM objects stay usable
after commit, §10), and a connect-time ``PRAGMA foreign_keys=ON`` enforces the §5.1 foreign keys.

The engine URL is config-driven (``$ARENA_DB_URL``, default ``./arena.db``); tests build a
throwaway engine via ``create_engine(<temp url>)`` so they never touch the dev database.
"""

import os
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

DEFAULT_DB_URL = "sqlite+aiosqlite:///./arena.db"


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model (server/models.py)."""


def _register_foreign_keys_pragma(engine: AsyncEngine) -> None:
    """Enable SQLite FK enforcement on every new DBAPI connection of ``engine``."""

    def _set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(engine.sync_engine, "connect", _set_sqlite_pragma)


def create_engine(db_url: str | None = None, **kwargs: Any) -> AsyncEngine:
    """Build an async engine with SQLite FK enforcement enabled.

    ``db_url`` defaults to ``$ARENA_DB_URL`` then ``./arena.db``; tests pass a throwaway URL.
    """
    url = db_url or os.environ.get("ARENA_DB_URL", DEFAULT_DB_URL)
    # NullPool: SQLite is a local file, so pooling buys little at MVP scale, and not retaining
    # connections keeps engine teardown clean (no lingering aiosqlite connections to terminate
    # across async tests) and re-runs the FK PRAGMA on every fresh connection.
    kwargs.setdefault("poolclass", NullPool)
    new_engine = create_async_engine(url, **kwargs)
    _register_foreign_keys_pragma(new_engine)
    return new_engine


def create_session_maker(bound_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session factory; ``expire_on_commit=False`` keeps ORM objects usable after commit (§10)."""
    return async_sessionmaker(bound_engine, expire_on_commit=False)


# Process-wide engine + session maker for the running app (config-driven URL). Building the engine
# opens no connection, so importing this module never creates ./arena.db.
engine: AsyncEngine = create_engine()
async_session_maker: async_sessionmaker[AsyncSession] = create_session_maker(engine)


async def init_models(target_engine: AsyncEngine | None = None) -> None:
    """Create every table (idempotent). Called from the FastAPI lifespan on startup.

    Imports ``server.models`` first so all tables are registered on ``Base.metadata`` before
    ``create_all`` runs.
    """
    from server import models  # noqa: F401  (registers the ORM tables on Base.metadata)

    eng = target_engine if target_engine is not None else engine
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
