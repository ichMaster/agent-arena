"""WS endpoint lifecycle tests (ARENA-OPUS-OPUS-013): token auth, joined, finally cleanup.
Real TestClient WebSocket connections against a throwaway DB; no LLM, no paid call.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from server.database import create_engine, create_session_maker
from server.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/ws.db")
    app = create_app(db_engine=engine, session_maker=create_session_maker(engine))
    with TestClient(app) as c:
        yield c


def _create_match(client: TestClient) -> str:
    return str(client.post("/api/v1/lobby/match").json()["match_id"])


def _join(client: TestClient, match_id: str, name: str, spectator: bool = False) -> str:
    body = {"match_id": match_id, "player_name": name, "spectator": spectator}
    return str(client.post("/api/v1/lobby/join", json=body).json()["token"])


def test_valid_token_connects_and_receives_joined(client: TestClient) -> None:
    match_id = _create_match(client)
    token = _join(client, match_id, "Alice")
    with client.websocket_connect(f"/ws/match/{match_id}?token={token}") as ws:
        msg = ws.receive_json()
    assert msg["event"] == "joined"
    assert msg["payload"]["symbol"] == "X"  # first joiner
    assert msg["payload"]["board"] == [""] * 9
    assert msg["payload"]["current_turn"] == "X"
    assert msg["payload"]["valid_moves"] == list(range(9))


def test_second_joiner_gets_o(client: TestClient) -> None:
    match_id = _create_match(client)
    ta, tb = _join(client, match_id, "A"), _join(client, match_id, "B")
    with client.websocket_connect(f"/ws/match/{match_id}?token={ta}") as wa:
        wa.receive_json()
        with client.websocket_connect(f"/ws/match/{match_id}?token={tb}") as wb:
            assert wb.receive_json()["payload"]["symbol"] == "O"


def test_spectator_gets_null_symbol(client: TestClient) -> None:
    match_id = _create_match(client)
    token = _join(client, match_id, "Watcher", spectator=True)
    with client.websocket_connect(f"/ws/match/{match_id}?token={token}") as ws:
        assert ws.receive_json()["payload"]["symbol"] is None


def test_missing_token_closes_4001(client: TestClient) -> None:
    match_id = _create_match(client)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/match/{match_id}") as ws:
            ws.receive_json()
    assert exc.value.code == 4001


def test_bad_token_closes_4001(client: TestClient) -> None:
    match_id = _create_match(client)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/match/{match_id}?token=garbage") as ws:
            ws.receive_json()
    assert exc.value.code == 4001


def test_disconnect_releases_the_seat_for_a_reclaim(client: TestClient) -> None:
    match_id = _create_match(client)
    token_a = _join(client, match_id, "Alice")
    with client.websocket_connect(f"/ws/match/{match_id}?token={token_a}") as ws:
        assert ws.receive_json()["payload"]["symbol"] == "X"
    # ws context exited -> disconnect -> the shielded finally releases the seat.
    token_b = _join(client, match_id, "Bob")
    with client.websocket_connect(f"/ws/match/{match_id}?token={token_b}") as ws2:
        assert ws2.receive_json()["payload"]["symbol"] == "X"  # reclaimed the freed seat


def test_unknown_action_yields_error(client: TestClient) -> None:
    match_id = _create_match(client)
    token = _join(client, match_id, "Alice")
    with client.websocket_connect(f"/ws/match/{match_id}?token={token}") as ws:
        ws.receive_json()  # joined
        ws.send_json({"action": "frobnicate", "payload": {}})
        resp = ws.receive_json()
    assert resp["event"] == "error"
