"""Auth tokens + the seat-by-token identity (architecture §5.2, §6.3).

The token is the participant PK; identity is keyed by token, not by display name. Throwaway DB,
no LLM, no paid call.
"""

import dataclasses

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from server.auth import IssuedToken, issue_token, validate_token
from server.repository import Repository


def test_issue_token_is_unique_and_opaque() -> None:
    first, second = issue_token(), issue_token()
    assert isinstance(first, str) and first
    assert first != second  # unique per call


def test_issued_token_shape_and_default() -> None:
    fields = [f.name for f in dataclasses.fields(IssuedToken)]
    assert fields == ["match_id", "player_name", "is_spectator"]
    token = IssuedToken(match_id="m", player_name="A")
    assert token.is_spectator is False  # default


def test_issued_token_is_frozen() -> None:
    token = IssuedToken(match_id="m", player_name="A")
    with pytest.raises(dataclasses.FrozenInstanceError):
        token.match_id = "other"  # type: ignore[misc]


async def test_validate_token_roundtrip(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        token = issue_token()
        await repo.add_participant(token, "m1", "Alice", is_spectator=False)
        issued = await validate_token(repo, "m1", token)
        assert issued is not None
        assert issued.match_id == "m1"
        assert issued.player_name == "Alice"
        assert issued.is_spectator is False


async def test_validate_unknown_token_is_none(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        assert await validate_token(repo, "m1", "ghost") is None


async def test_validate_token_from_other_match_is_none(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        await repo.create_match("m2")
        token = issue_token()
        await repo.add_participant(token, "m1", "Alice", is_spectator=False)
        assert await validate_token(repo, "m2", token) is None  # token belongs to m1


async def test_identity_keyed_by_token_not_name(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        token_a, token_b = issue_token(), issue_token()
        await repo.add_participant(token_a, "m1", "Human", is_spectator=False)
        await repo.add_participant(token_b, "m1", "Human", is_spectator=False)
        identity_a = await validate_token(repo, "m1", token_a)
        identity_b = await validate_token(repo, "m1", token_b)
        assert identity_a is not None and identity_b is not None
        assert token_a != token_b  # same name, distinct tokens
        assert identity_a.player_name == identity_b.player_name == "Human"
