"""Lobby REST tests (ARENA-OPUS-OPUS-010): create + join, 404, observer flag. Throwaway DB, no LLM."""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from server.database import create_engine, create_session_maker, init_models
from server.main import create_app
from server.repository import Repository


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/lobby.db")
    app = create_app(db_engine=engine, session_maker=create_session_maker(engine))
    with TestClient(app) as c:
        yield c


def test_create_match_returns_id(client: TestClient) -> None:
    resp = client.post("/api/v1/lobby/match")
    assert resp.status_code == 200
    assert "match_id" in resp.json() and len(resp.json()["match_id"]) > 0


def test_create_then_join_returns_token(client: TestClient) -> None:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    resp = client.post(
        "/api/v1/lobby/join", json={"match_id": match_id, "player_name": "Alice"}
    )
    assert resp.status_code == 200
    assert len(resp.json()["token"]) > 0


def test_join_unknown_match_404s(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/lobby/join", json={"match_id": "nope", "player_name": "Alice"}
    )
    assert resp.status_code == 404


def test_spectator_join_is_stored_as_observer(client: TestClient, tmp_path: Path) -> None:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    token = client.post(
        "/api/v1/lobby/join",
        json={"match_id": match_id, "player_name": "Watcher", "spectator": True},
    ).json()["token"]

    # Re-open the DB directly to confirm the observer flag persisted.
    async def _check() -> bool:
        engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/lobby.db")
        maker = create_session_maker(engine)
        async with maker() as session:
            p = await Repository(session).get_participant(token)
        await engine.dispose()
        return p is not None and p.is_spectator is True

    import asyncio

    assert asyncio.run(_check()) is True
