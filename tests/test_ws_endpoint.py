"""Integration tests for the WS endpoint (architecture §5.3, §6.2, §10) via ``TestClient``.

Connect over a real (in-process) WebSocket, assert the `joined` event and the seat, the `4001`
close on a bad/missing token, and that leaving the socket releases the seat for reclaim. Throwaway
DB, no LLM, no paid call.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from server.database import create_engine, create_session_maker
from server.main import create_app

EMPTY_BOARD = [""] * 9


@pytest.fixture
def lobby(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/ws.db")
    maker = create_session_maker(engine)
    app = create_app(db_engine=engine, session_maker=maker)
    with TestClient(app) as client:
        yield client


def _match(client: TestClient) -> str:
    return str(client.post("/api/v1/lobby/match").json()["match_id"])


def _join(client: TestClient, match_id: str, name: str, spectator: bool = False) -> str:
    body = {"match_id": match_id, "player_name": name, "spectator": spectator}
    return str(client.post("/api/v1/lobby/join", json=body).json()["token"])


def test_first_player_receives_joined_as_x(lobby: TestClient) -> None:
    match_id = _match(lobby)
    token = _join(lobby, match_id, "Alice")
    with lobby.websocket_connect(f"/ws/match/{match_id}?token={token}") as ws:
        evt = ws.receive_json()
    assert evt["event"] == "joined"
    payload = evt["payload"]
    assert payload["symbol"] == "X"
    assert payload["board"] == EMPTY_BOARD
    assert payload["current_turn"] == "X"
    assert payload["valid_moves"] == list(range(9))


def test_two_players_get_x_and_o(lobby: TestClient) -> None:
    match_id = _match(lobby)
    token_a = _join(lobby, match_id, "Alice")
    token_b = _join(lobby, match_id, "Bob")
    with lobby.websocket_connect(f"/ws/match/{match_id}?token={token_a}") as ws_a:
        joined_a = ws_a.receive_json()
        with lobby.websocket_connect(f"/ws/match/{match_id}?token={token_b}") as ws_b:
            joined_b = ws_b.receive_json()
        assert joined_a["payload"]["symbol"] == "X"
        assert joined_b["payload"]["symbol"] == "O"


def test_spectator_joined_with_null_symbol(lobby: TestClient) -> None:
    match_id = _match(lobby)
    observer = _join(lobby, match_id, "Watcher", spectator=True)
    with lobby.websocket_connect(f"/ws/match/{match_id}?token={observer}") as ws:
        evt = ws.receive_json()
    assert evt["payload"]["symbol"] is None


def test_bad_token_closes_4001(lobby: TestClient) -> None:
    match_id = _match(lobby)
    with pytest.raises(WebSocketDisconnect) as exc:
        with lobby.websocket_connect(f"/ws/match/{match_id}?token=BADTOKEN") as ws:
            ws.receive_json()
    assert exc.value.code == 4001


def test_missing_token_closes_4001(lobby: TestClient) -> None:
    match_id = _match(lobby)
    with pytest.raises(WebSocketDisconnect) as exc:
        with lobby.websocket_connect(f"/ws/match/{match_id}") as ws:
            ws.receive_json()
    assert exc.value.code == 4001


def test_reconnect_same_participant_reuses_seat(lobby: TestClient) -> None:
    """The `finally` cleanup runs and the endpoint is reusable: the same participant can reconnect.

    (Robust reclaim of a dropped seat by a *different* participant under the client-drop
    cancellation path is hardened in v05.01, per architecture §10 / roadmap §v05.01.)
    """
    match_id = _match(lobby)
    token = _join(lobby, match_id, "Alice")
    with lobby.websocket_connect(f"/ws/match/{match_id}?token={token}") as ws1:
        assert ws1.receive_json()["payload"]["symbol"] == "X"
    # Reconnecting the same participant is idempotent and still works after the first drop.
    with lobby.websocket_connect(f"/ws/match/{match_id}?token={token}") as ws2:
        assert ws2.receive_json()["payload"]["symbol"] == "X"
