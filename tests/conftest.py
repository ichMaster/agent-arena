"""Shared test fixtures — a throwaway SQLite DB per test (temp file, ``foreign_keys=ON``).

The dev ``./arena.db`` is never touched, and no LLM is involved anywhere in the suite.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from server.database import create_engine, create_session_maker, init_models


@pytest_asyncio.fixture
async def db_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """A fresh temp-file SQLite engine with the schema created and FK enforcement on."""
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_maker(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """A session factory bound to the throwaway engine."""
    return create_session_maker(db_engine)
