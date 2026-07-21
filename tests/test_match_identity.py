"""End-to-end seat-by-token identity (ARENA-OPUS-OPUS-011): real join tokens -> seats via match.py.

Throwaway DB, no LLM, no paid call. Proves the v01.03 DoD: distinct tokens get X/O, a third gets no
seat, a spectator is never seated, and two joins named "Human" stay distinct by token.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from server import match
from server.database import create_engine, create_session_maker
from server.main import create_app


@pytest.fixture
def env(tmp_path: Path) -> Iterator[tuple[TestClient, async_sessionmaker]]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/identity.db")
    maker = create_session_maker(engine)
    app = create_app(db_engine=engine, session_maker=maker)
    with TestClient(app) as c:
        yield c, maker


def _join(client: TestClient, match_id: str, name: str, spectator: bool = False) -> str:
    body = {"match_id": match_id, "player_name": name, "spectator": spectator}
    return str(client.post("/api/v1/lobby/join", json=body).json()["token"])


async def test_two_tokens_get_x_and_o_third_none(
    env: tuple[TestClient, async_sessionmaker],
) -> None:
    client, maker = env
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    t1, t2, t3 = (_join(client, match_id, n) for n in ("A", "B", "C"))
    assert await match.assign_symbol(maker, match_id, t1) == "X"
    assert await match.assign_symbol(maker, match_id, t2) == "O"
    assert await match.assign_symbol(maker, match_id, t3) is None


async def test_spectator_never_seated(
    env: tuple[TestClient, async_sessionmaker],
) -> None:
    client, maker = env
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    obs = _join(client, match_id, "Watcher", spectator=True)
    assert await match.assign_symbol(maker, match_id, obs) is None


async def test_same_name_joins_stay_distinct_by_token(
    env: tuple[TestClient, async_sessionmaker],
) -> None:
    client, maker = env
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    t1 = _join(client, match_id, "Human")
    t2 = _join(client, match_id, "Human")  # same display name
    assert t1 != t2
    assert await match.assign_symbol(maker, match_id, t1) == "X"
    assert await match.assign_symbol(maker, match_id, t2) == "O"  # distinct seat, not merged


async def test_release_frees_the_seat(
    env: tuple[TestClient, async_sessionmaker],
) -> None:
    client, maker = env
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    t1 = _join(client, match_id, "A")
    assert await match.assign_symbol(maker, match_id, t1) == "X"
    await match.release_seat(maker, match_id, t1)
    t2 = _join(client, match_id, "B")
    assert await match.assign_symbol(maker, match_id, t2) == "X"  # reclaimed
