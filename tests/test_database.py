"""Schema/engine tests for the persistence gate (ARENA-OPUS-OPUS-004). Throwaway temp-file DB, no
LLM, no paid call. Pins the four table shapes and confirms FK enforcement + seat uniqueness.
"""

from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from server.database import Base, create_engine, create_session_maker, init_models
from server.models import ChatMessage, Match, Move, Participant


def _url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path}/arena.db"


async def test_init_models_creates_the_four_tables(tmp_path: Path) -> None:
    engine = create_engine(_url(tmp_path))
    await init_models(engine)
    async with engine.connect() as conn:
        names = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert names == {"matches", "participants", "moves", "chat_messages"}
    await engine.dispose()


def test_table_shapes_are_pinned() -> None:
    # Contract: table names + the seat-uniqueness constraint (roadmap §v01.02 Tests).
    assert Match.__tablename__ == "matches"
    assert Participant.__tablename__ == "participants"
    assert Move.__tablename__ == "moves"
    assert ChatMessage.__tablename__ == "chat_messages"
    assert Match.__table__.primary_key.columns.keys() == ["match_id"]
    assert Participant.__table__.primary_key.columns.keys() == ["token"]
    # UNIQUE(match_id, symbol) is present on participants.
    uniques = [
        tuple(c.name for c in con.columns)
        for con in Participant.__table__.constraints
        if con.__class__.__name__ == "UniqueConstraint"
    ]
    assert ("match_id", "symbol") in uniques


async def test_foreign_keys_are_enforced(tmp_path: Path) -> None:
    engine = create_engine(_url(tmp_path))
    await init_models(engine)
    maker = create_session_maker(engine)
    async with maker() as session:
        session.add(Move(match_id="ghost", player_symbol="X", move=0))  # no such match
        with pytest.raises(IntegrityError):
            await session.commit()
    await engine.dispose()


async def test_foreign_keys_pragma_is_on(tmp_path: Path) -> None:
    engine = create_engine(_url(tmp_path))
    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA foreign_keys"))
        assert result.scalar() == 1
    await engine.dispose()


async def test_duplicate_seat_symbol_rejected(tmp_path: Path) -> None:
    engine = create_engine(_url(tmp_path))
    await init_models(engine)
    maker = create_session_maker(engine)
    async with maker() as session:
        session.add(Match(match_id="m1"))
        session.add(Participant(token="t1", match_id="m1", player_name="A", symbol="X"))
        session.add(Participant(token="t2", match_id="m1", player_name="B", symbol="X"))
        with pytest.raises(IntegrityError):
            await session.commit()
    await engine.dispose()
