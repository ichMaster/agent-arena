"""Auth-token / seat-by-token identity tests (ARENA-OPUS-OPUS-009). Throwaway DB, no LLM, no paid call.

Pins the identity surface: identity is the token (the participant PK), never the display name.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

from server.auth import IssuedToken, issue_token, validate_token
from server.database import create_engine, create_session_maker, init_models
from server.repository import Repository


@pytest_asyncio.fixture
async def repo(tmp_path: Path) -> AsyncIterator[Repository]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/auth.db")
    await init_models(engine)
    maker = create_session_maker(engine)
    async with maker() as session:
        yield Repository(session)
    await engine.dispose()


def test_issue_token_is_unique_and_opaque() -> None:
    tokens = {issue_token() for _ in range(100)}
    assert len(tokens) == 100  # no collisions
    assert all(len(t) > 20 for t in tokens)


def test_issued_token_shape_defaults_spectator_false() -> None:
    tok = IssuedToken(match_id="m1", player_name="Alice")
    assert tok.is_spectator is False
    assert tok.match_id == "m1" and tok.player_name == "Alice"


async def test_validate_returns_issued_token_for_a_real_participant(repo: Repository) -> None:
    await repo.create_match("m1")
    token = issue_token()
    await repo.add_participant(token, "m1", "Alice")
    resolved = await validate_token(repo, "m1", token)
    assert resolved == IssuedToken(match_id="m1", player_name="Alice", is_spectator=False)


async def test_validate_rejects_unknown_token(repo: Repository) -> None:
    await repo.create_match("m1")
    assert await validate_token(repo, "m1", "no-such-token") is None


async def test_validate_rejects_token_from_a_different_match(repo: Repository) -> None:
    await repo.create_match("m1")
    await repo.create_match("m2")
    token = issue_token()
    await repo.add_participant(token, "m1", "Alice")
    assert await validate_token(repo, "m2", token) is None  # right token, wrong match


async def test_identity_is_by_token_not_name(repo: Repository) -> None:
    await repo.create_match("m1")
    t1, t2 = issue_token(), issue_token()
    await repo.add_participant(t1, "m1", "Human")
    await repo.add_participant(t2, "m1", "Human")  # same display name, different token
    assert t1 != t2
    # Both resolve, and to distinct participant rows (the PK is the token).
    assert (await repo.get_participant(t1)).token != (await repo.get_participant(t2)).token  # type: ignore[union-attr]
