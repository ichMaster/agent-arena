"""Shared test fixtures — a throwaway SQLite DB per test (temp file, ``foreign_keys=ON``).

The dev ``./arena.db`` is never touched, and no LLM is involved anywhere in the suite — the latter is
now enforced mechanically by the autouse ``_guard_no_paid_call`` fixture below (§11).
"""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from server.database import create_engine, create_session_maker, init_models


@pytest.fixture(autouse=True)
def _guard_no_paid_call() -> Iterator[None]:
    """No test may reach the Anthropic API (§11). Patch the SDK client to a dummy for **every** test,
    so even an un-mocked ``create_llm_client`` cannot open a network connection. Tests that patch
    ``agent.llm.AsyncAnthropic`` themselves still override this locally (nested patch)."""
    with patch("agent.llm.AsyncAnthropic", new=MagicMock()):
        yield


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
