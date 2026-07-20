"""Tests for the §5.2 seat rule at the Repository level (`assign_symbol` / `release_seat`).

Seats are keyed by token, never by display name; spectators never get a seat. Throwaway DB, no LLM.
The full token/REST identity coverage (name-collision over the lobby) lands in v01.03.
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from server.repository import Repository


async def test_first_two_tokens_get_x_and_o(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        await repo.add_participant("t1", "m1", "A", is_spectator=False)
        await repo.add_participant("t2", "m1", "B", is_spectator=False)
        assert await repo.assign_symbol("m1", "t1") == "X"
        assert await repo.assign_symbol("m1", "t2") == "O"


async def test_third_player_gets_none(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        for token in ("t1", "t2", "t3"):
            await repo.add_participant(token, "m1", token, is_spectator=False)
        assert await repo.assign_symbol("m1", "t1") == "X"
        assert await repo.assign_symbol("m1", "t2") == "O"
        assert await repo.assign_symbol("m1", "t3") is None  # match full


async def test_spectator_never_seated(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        await repo.add_participant("obs", "m1", "Observer", is_spectator=True)
        assert await repo.assign_symbol("m1", "obs") is None


async def test_assign_is_idempotent(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        await repo.add_participant("t1", "m1", "A", is_spectator=False)
        first = await repo.assign_symbol("m1", "t1")
        again = await repo.assign_symbol("m1", "t1")
        assert first == "X" and again == "X"  # reconnect returns the same seat


async def test_release_seat_frees_symbol_for_reclaim(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        await repo.add_participant("t1", "m1", "A", is_spectator=False)
        await repo.add_participant("t2", "m1", "B", is_spectator=False)
        assert await repo.assign_symbol("m1", "t1") == "X"
        assert await repo.assign_symbol("m1", "t2") == "O"
        await repo.release_seat("m1", "t1")  # X is now free
        await repo.add_participant("t3", "m1", "C", is_spectator=False)
        assert await repo.assign_symbol("m1", "t3") == "X"  # reclaims the freed seat


async def test_same_display_name_gets_distinct_seats(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        # Both named "Human" — keyed by token, they must NOT merge onto one seat.
        await repo.add_participant("t1", "m1", "Human", is_spectator=False)
        await repo.add_participant("t2", "m1", "Human", is_spectator=False)
        assert await repo.assign_symbol("m1", "t1") == "X"
        assert await repo.assign_symbol("m1", "t2") == "O"


async def test_unknown_token_returns_none(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        assert await repo.assign_symbol("m1", "ghost") is None


async def test_concurrent_assign_resolves_to_distinct_seats(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Two connections claiming a seat at the same instant get X and O — no IntegrityError crash.

    Regression for the seat race: each assign runs on its own session (like two WebSocket
    connections); the UNIQUE(match_id, symbol) guard + retry must resolve them to distinct symbols.
    """
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        await repo.add_participant("t1", "m1", "A", is_spectator=False)
        await repo.add_participant("t2", "m1", "B", is_spectator=False)

    async def assign(token: str) -> str | None:
        async with session_maker() as session:
            return await Repository(session).assign_symbol("m1", token)

    first, second = await asyncio.gather(assign("t1"), assign("t2"))
    assert {first, second} == {"X", "O"}  # both seated, distinctly, with no exception
