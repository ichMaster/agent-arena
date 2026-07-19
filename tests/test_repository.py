"""Unit/integration tests for the Repository CRUD (architecture §5.1) on a throwaway SQLite DB.

Round-trips each table, checks ordering and the unknown-id / FK-violation paths, and verifies
persistence survives a fresh engine (a simulated restart). No LLM, no paid call.
"""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from server.database import create_engine, create_session_maker, init_models
from server.models import ChatMessage, Move, Participant
from server.repository import Repository


async def test_create_and_get_match(session_maker: async_sessionmaker[AsyncSession]) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        match = await repo.get_match("m1")
        assert match is not None
        assert match.match_id == "m1"
        assert match.game_type == "tictactoe"
        assert match.status == "active"


async def test_get_match_unknown_returns_none(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        assert await Repository(session).get_match("nope") is None


async def test_add_participant_roundtrip(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        await repo.add_participant("t1", "m1", "Alice", is_spectator=False)
        await repo.add_participant("t2", "m1", "Bob", is_spectator=True)
        p1 = await session.get(Participant, "t1")
        p2 = await session.get(Participant, "t2")
        assert p1 is not None and p1.player_name == "Alice" and p1.is_spectator is False
        assert p2 is not None and p2.player_name == "Bob" and p2.is_spectator is True
        assert p1.symbol is None and p2.symbol is None  # unseated until assign_symbol


async def test_moves_persist_in_insertion_order(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        for symbol, cell in [("X", 0), ("O", 4), ("X", 1)]:
            await repo.log_move("m1", symbol, cell)
        rows = (
            await session.execute(select(Move).where(Move.match_id == "m1").order_by(Move.id))
        ).scalars().all()
        assert [(r.player_symbol, r.move) for r in rows] == [("X", 0), ("O", 4), ("X", 1)]


async def test_chat_persists_in_insertion_order(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        await repo.log_chat("m1", "X", "hi")
        await repo.log_chat("m1", "O", "you'll lose")
        rows = (
            await session.execute(
                select(ChatMessage).where(ChatMessage.match_id == "m1").order_by(ChatMessage.id)
            )
        ).scalars().all()
        assert [(r.sender, r.message) for r in rows] == [("X", "hi"), ("O", "you'll lose")]


async def test_log_move_for_missing_match_rejected(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        with pytest.raises(IntegrityError):  # FK: no such match
            await Repository(session).log_move("ghost", "X", 0)


async def test_add_participant_for_missing_match_rejected(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        with pytest.raises(IntegrityError):  # FK: no such match
            await Repository(session).add_participant("t1", "ghost", "A", is_spectator=False)


async def test_state_survives_a_fresh_engine(tmp_path: Path) -> None:
    """Durability: write with one engine, read it back with a new engine on the same file."""
    url = f"sqlite+aiosqlite:///{tmp_path}/restart.db"

    engine1 = create_engine(url)
    await init_models(engine1)
    async with create_session_maker(engine1)() as session:
        repo = Repository(session)
        await repo.create_match("persist")
        await repo.log_move("persist", "X", 4)
    await engine1.dispose()

    engine2 = create_engine(url)  # simulate a server restart
    async with create_session_maker(engine2)() as session:
        repo = Repository(session)
        match = await repo.get_match("persist")
        assert match is not None
        rows = (
            await session.execute(select(Move).where(Move.match_id == "persist"))
        ).scalars().all()
        assert [(r.player_symbol, r.move) for r in rows] == [("X", 4)]
    await engine2.dispose()
