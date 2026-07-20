"""Integration test for the WS `chat` handler (architecture §3.5, §6.2) via ``TestClient``.

Two WebSocket connections: one sends a `chat` action; both receive the `chat_message`, and it is
persisted. Throwaway DB, no LLM, no paid call.
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.database import create_engine, create_session_maker
from server.main import create_app

DB_NAME = "chat.db"


@pytest.fixture
def lobby(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/{DB_NAME}")
    maker = create_session_maker(engine)
    app = create_app(db_engine=engine, session_maker=maker)
    with TestClient(app) as client:
        yield client


def _match(client: TestClient) -> str:
    return str(client.post("/api/v1/lobby/match").json()["match_id"])


def _join(client: TestClient, match_id: str, name: str, spectator: bool = False) -> str:
    body = {"match_id": match_id, "player_name": name, "spectator": spectator}
    return str(client.post("/api/v1/lobby/join", json=body).json()["token"])


def test_chat_is_broadcast_to_all_and_persisted(lobby: TestClient, tmp_path: Path) -> None:
    match_id = _match(lobby)
    token_x = _join(lobby, match_id, "Alice")
    token_o = _join(lobby, match_id, "Bob")
    with lobby.websocket_connect(f"/ws/match/{match_id}?token={token_x}") as ws_x:
        ws_x.receive_json()  # joined X
        with lobby.websocket_connect(f"/ws/match/{match_id}?token={token_o}") as ws_o:
            ws_o.receive_json()  # joined O
            ws_x.send_json({"action": "chat", "payload": {"message": "prepare to lose"}})
            msg_x = ws_x.receive_json()
            msg_o = ws_o.receive_json()

    expected = {"sender": "X", "message": "prepare to lose"}
    assert msg_x["event"] == "chat_message" and msg_x["payload"] == expected
    assert msg_o["event"] == "chat_message" and msg_o["payload"] == expected

    # Persisted to chat_messages.
    connection = sqlite3.connect(tmp_path / DB_NAME)
    try:
        rows = connection.execute("SELECT sender, message FROM chat_messages").fetchall()
    finally:
        connection.close()
    assert ("X", "prepare to lose") in rows


def test_observer_chat_is_rejected(lobby: TestClient, tmp_path: Path) -> None:
    """A spectator cannot post chat — the server (authority) rejects it (§3.3)."""
    match_id = _match(lobby)
    observer = _join(lobby, match_id, "Watcher", spectator=True)
    with lobby.websocket_connect(f"/ws/match/{match_id}?token={observer}") as ws:
        ws.receive_json()  # joined with symbol null
        ws.send_json({"action": "chat", "payload": {"message": "sneaky"}})
        evt = ws.receive_json()
    assert evt["event"] == "error"
    assert "observer" in evt["payload"]["detail"].lower()

    # Nothing was persisted.
    connection = sqlite3.connect(tmp_path / DB_NAME)
    try:
        count = connection.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
    finally:
        connection.close()
    assert count == 0
