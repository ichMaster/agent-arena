"""Seat-assignment tests pinning the §5.2 rule at the Repository level (ARENA-OPUS-OPUS-006).

Throwaway DB, no LLM, no paid call. Covers the four §5.2 cases, release/reclaim, and a real
concurrency race resolved by the UNIQUE constraint + retry.
"""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

from server.database import create_engine, create_session_maker, init_models
from server.repository import Repository


@pytest_asyncio.fixture
async def repo(tmp_path: Path) -> AsyncIterator[Repository]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/arena.db")
    await init_models(engine)
    maker = create_session_maker(engine)
    async with maker() as session:
        yield Repository(session)
    await engine.dispose()


async def test_first_two_tokens_get_x_and_o(repo: Repository) -> None:
    await repo.create_match("m1")
    await repo.add_participant("t1", "m1", "A")
    await repo.add_participant("t2", "m1", "B")
    assert await repo.assign_symbol("m1", "t1") == "X"
    assert await repo.assign_symbol("m1", "t2") == "O"


async def test_third_participant_gets_none(repo: Repository) -> None:
    await repo.create_match("m1")
    for tok in ("t1", "t2", "t3"):
        await repo.add_participant(tok, "m1", tok)
    await repo.assign_symbol("m1", "t1")
    await repo.assign_symbol("m1", "t2")
    assert await repo.assign_symbol("m1", "t3") is None  # match full


async def test_spectator_never_seated(repo: Repository) -> None:
    await repo.create_match("m1")
    await repo.add_participant("obs", "m1", "Watcher", is_spectator=True)
    assert await repo.assign_symbol("m1", "obs") is None


async def test_reassign_is_idempotent(repo: Repository) -> None:
    await repo.create_match("m1")
    await repo.add_participant("t1", "m1", "A")
    first = await repo.assign_symbol("m1", "t1")
    assert first == "X"
    assert await repo.assign_symbol("m1", "t1") == "X"  # same seat, no second seat consumed


async def test_unknown_token_returns_none(repo: Repository) -> None:
    await repo.create_match("m1")
    assert await repo.assign_symbol("m1", "ghost") is None


async def test_release_then_reclaim(repo: Repository) -> None:
    await repo.create_match("m1")
    await repo.add_participant("t1", "m1", "A")
    await repo.add_participant("t2", "m1", "B")
    assert await repo.assign_symbol("m1", "t1") == "X"
    await repo.release_seat("m1", "t1")
    # A fresh participant reclaims the freed X.
    await repo.add_participant("t3", "m1", "C")
    assert await repo.assign_symbol("m1", "t3") == "X"


async def test_concurrent_assign_resolves_to_distinct_seats(tmp_path: Path) -> None:
    """Two tokens race for seats on separate sessions; the UNIQUE guard + retry gives them X and O
    (never the same symbol twice, never an uncaught IntegrityError)."""
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/race.db")
    await init_models(engine)
    maker = create_session_maker(engine)
    async with maker() as s0:
        setup = Repository(s0)
        await setup.create_match("m1")
        await setup.add_participant("t1", "m1", "A")
        await setup.add_participant("t2", "m1", "B")

    async def claim(token: str) -> str | None:
        async with maker() as session:
            return await Repository(session).assign_symbol("m1", token)

    results = await asyncio.gather(claim("t1"), claim("t2"))
    assert set(results) == {"X", "O"}  # distinct seats, both real
    await engine.dispose()
