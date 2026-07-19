"""Unit tests for the persistence layer against a throwaway SQLite DB (``foreign_keys=ON``).

Verifies ``init_models`` creates the schema, the FK PRAGMA is on, and the DB-level guards
(seat uniqueness, foreign keys) actually fire. No dev DB, no LLM, no paid call.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from server.models import Match, Move, Participant


async def test_init_models_creates_all_tables(db_engine: AsyncEngine) -> None:
    async with db_engine.connect() as conn:
        rows = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        names = {row[0] for row in rows}
    assert {"matches", "participants", "moves", "chat_messages"} <= names


async def test_foreign_keys_pragma_is_on(db_engine: AsyncEngine) -> None:
    async with db_engine.connect() as conn:
        result = await conn.execute(text("PRAGMA foreign_keys"))
        assert result.scalar() == 1


async def test_duplicate_seat_symbol_rejected(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        session.add(Match(match_id="m1"))
        session.add(Participant(token="t1", match_id="m1", player_name="A", symbol="X"))
        session.add(Participant(token="t2", match_id="m1", player_name="B", symbol="X"))
        with pytest.raises(IntegrityError):  # UNIQUE(match_id, symbol)
            await session.commit()


async def test_fk_violation_rejected(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        # No match "ghost" exists -> the FK on moves.match_id must reject the insert.
        session.add(Move(match_id="ghost", player_symbol="X", move=0))
        with pytest.raises(IntegrityError):
            await session.commit()
