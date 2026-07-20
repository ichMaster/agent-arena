"""Integration tests for the lobby REST endpoints (architecture §6.1) via ``TestClient``.

Create a match, join it (player or spectator), and confirm the 404 path — each against a throwaway
temp-file DB. No LLM, no paid call.
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.database import create_engine, create_session_maker
from server.main import create_app

DB_NAME = "lobby.db"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/{DB_NAME}")
    maker = create_session_maker(engine)
    app = create_app(db_engine=engine, session_maker=maker)
    with TestClient(app) as test_client:
        yield test_client


def test_create_then_join_returns_token(client: TestClient) -> None:
    created = client.post("/api/v1/lobby/match")
    assert created.status_code == 200
    match_id = created.json()["match_id"]
    assert match_id

    joined = client.post(
        "/api/v1/lobby/join", json={"match_id": match_id, "player_name": "Alice"}
    )
    assert joined.status_code == 200
    assert joined.json()["token"]


def test_join_unknown_match_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/lobby/join", json={"match_id": "does-not-exist", "player_name": "Alice"}
    )
    assert response.status_code == 404


def test_join_empty_player_name_returns_400(client: TestClient) -> None:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    for bad_name in ["", "   "]:
        response = client.post(
            "/api/v1/lobby/join", json={"match_id": match_id, "player_name": bad_name}
        )
        assert response.status_code == 400


def test_spectator_join_is_flagged_as_observer(client: TestClient, tmp_path: Path) -> None:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    token = client.post(
        "/api/v1/lobby/join",
        json={"match_id": match_id, "player_name": "Watcher", "spectator": True},
    ).json()["token"]

    # Read the persisted row directly to confirm is_spectator was stored.
    connection = sqlite3.connect(tmp_path / DB_NAME)
    try:
        row = connection.execute(
            "SELECT is_spectator FROM participants WHERE token = ?", (token,)
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    assert bool(row[0]) is True


def test_default_join_is_not_spectator(client: TestClient, tmp_path: Path) -> None:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    token = client.post(
        "/api/v1/lobby/join", json={"match_id": match_id, "player_name": "Alice"}
    ).json()["token"]
    connection = sqlite3.connect(tmp_path / DB_NAME)
    try:
        row = connection.execute(
            "SELECT is_spectator FROM participants WHERE token = ?", (token,)
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    assert bool(row[0]) is False
