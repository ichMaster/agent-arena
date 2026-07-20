"""Regression tests for the HARDEN sweep — v01.04 review findings #4 and #2.

#4: malformed WebSocket JSON yields an `error` event and KEEPS the connection.
#2: a dropped player's seat is released (cancellation-safe cleanup) so another participant can
reclaim it. Throwaway DB; no LLM.
"""

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.database import create_engine, create_session_maker
from server.main import create_app


@pytest.fixture
def lobby(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/resil.db")
    app = create_app(db_engine=engine, session_maker=create_session_maker(engine))
    with TestClient(app) as client:
        yield client


def _join(client: TestClient, match_id: str, name: str) -> str:
    body = {"match_id": match_id, "player_name": name}
    return str(client.post("/api/v1/lobby/join", json=body).json()["token"])


def test_malformed_json_keeps_connection(lobby: TestClient) -> None:
    """Review #4: garbage input → error event, and the socket still works afterwards."""
    match_id = lobby.post("/api/v1/lobby/match").json()["match_id"]
    token = _join(lobby, match_id, "Alice")
    with lobby.websocket_connect(f"/ws/match/{match_id}?token={token}") as ws:
        ws.receive_json()  # joined
        ws.send_text("{this is not json")
        err = ws.receive_json()
        assert err["event"] == "error" and "malformed" in err["payload"]["detail"].lower()

        ws.send_text('"a bare string is valid JSON but not a message"')
        err2 = ws.receive_json()
        assert err2["event"] == "error"

        ws.send_json({"action": "chat", "payload": {"message": "still alive"}})
        chat = ws.receive_json()  # the connection survived and still serves actions
        assert chat["event"] == "chat_message"
        assert chat["payload"]["message"] == "still alive"


def test_dropped_seat_reclaimable_by_another_participant(lobby: TestClient) -> None:
    """Review #2: player A drops mid-match; participant B can take the freed X seat."""
    match_id = lobby.post("/api/v1/lobby/match").json()["match_id"]
    token_a = _join(lobby, match_id, "Alice")
    token_b = _join(lobby, match_id, "Bob")

    with lobby.websocket_connect(f"/ws/match/{match_id}?token={token_a}") as ws_a:
        assert ws_a.receive_json()["payload"]["symbol"] == "X"
    # A's socket dropped (client-initiated) — the shielded cleanup must release X.

    symbol = None
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:  # the shielded release may land moments after the drop
        with lobby.websocket_connect(f"/ws/match/{match_id}?token={token_b}") as ws_b:
            symbol = ws_b.receive_json()["payload"]["symbol"]
        if symbol == "X":
            break
        time.sleep(0.05)
    assert symbol == "X"  # B reclaimed the seat A dropped
