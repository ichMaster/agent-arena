"""Repository CRUD round-trip tests (ARENA-OPUS-OPUS-005). Throwaway DB, no LLM, no paid call."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError

from server.database import create_engine, create_session_maker, init_models
from server.models import ChatMessage, Move
from server.repository import Repository
from sqlalchemy import select


@pytest_asyncio.fixture
async def repo(tmp_path: Path) -> AsyncIterator[Repository]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/arena.db")
    await init_models(engine)
    maker = create_session_maker(engine)
    async with maker() as session:
        yield Repository(session)
    await engine.dispose()


async def test_create_and_get_match(repo: Repository) -> None:
    await repo.create_match("m1")
    match = await repo.get_match("m1")
    assert match is not None
    assert match.match_id == "m1"
    assert match.game_type == "tictactoe"
    assert match.status == "active"


async def test_get_unknown_match_returns_none(repo: Repository) -> None:
    assert await repo.get_match("nope") is None


async def test_add_and_get_participant(repo: Repository) -> None:
    await repo.create_match("m1")
    await repo.add_participant("tok", "m1", "Alice")
    p = await repo.get_participant("tok")
    assert p is not None
    assert p.player_name == "Alice" and p.symbol is None and p.is_spectator is False


async def test_moves_return_in_insertion_order(repo: Repository) -> None:
    await repo.create_match("m1")
    for cell in (4, 0, 8, 2):
        await repo.log_move("m1", "X" if cell % 2 == 0 else "O", cell)
    moves = await repo._moves_in_order("m1")
    assert [m.move for m in moves] == [4, 0, 8, 2]


async def test_chat_round_trips(repo: Repository) -> None:
    await repo.create_match("m1")
    await repo.log_chat("m1", "X", "hello")
    rows = (await repo._session.execute(select(ChatMessage))).scalars().all()
    assert [(r.sender, r.message) for r in rows] == [("X", "hello")]


async def test_move_for_missing_match_is_rejected(repo: Repository) -> None:
    with pytest.raises(IntegrityError):
        await repo.log_move("ghost", "X", 0)


async def test_opaque_move_payload_persists_as_is(repo: Repository) -> None:
    await repo.create_match("m1")
    # The store must not interpret the payload; a dict round-trips untouched.
    await repo.log_move("m1", "X", {"from": "e2", "to": "e4"})
    moves = await repo._moves_in_order("m1")
    assert moves[0].move == {"from": "e2", "to": "e4"}


async def test_persistence_survives_a_fresh_engine(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path}/arena.db"
    engine = create_engine(url)
    await init_models(engine)
    maker = create_session_maker(engine)
    async with maker() as session:
        await Repository(session).create_match("persisted")
    await engine.dispose()

    # A brand-new engine on the same file still sees the match (restart simulation).
    engine2 = create_engine(url)
    maker2 = create_session_maker(engine2)
    async with maker2() as session:
        assert await Repository(session).get_match("persisted") is not None
    await engine2.dispose()
