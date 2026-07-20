"""Integration tests for the §5.4 move-authority flow + game_over/close_room via ``TestClient``.

Two WebSocket connections play a full server-validated game to a win and to a draw; out-of-turn,
illegal, and no-seat moves are rejected; the terminal `state_update` carries `current_turn: null`,
then `game_over` is broadcast and the room closed. Throwaway DB, no LLM, no paid call.
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.database import create_engine, create_session_maker
from server.main import create_app

DB_NAME = "game.db"


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


def _submit(ws: Any, move: Any) -> None:
    ws.send_json({"action": "submit_move", "payload": {"move": move}})


def _match_row(tmp_path: Path, match_id: str) -> tuple[Any, ...] | None:
    connection = sqlite3.connect(tmp_path / DB_NAME)
    try:
        return connection.execute(
            "SELECT status, result FROM matches WHERE match_id = ?", (match_id,)
        ).fetchone()
    finally:
        connection.close()


def test_full_game_x_wins(lobby: TestClient, tmp_path: Path) -> None:
    match_id = _match(lobby)
    token_x = _join(lobby, match_id, "Xp")
    token_o = _join(lobby, match_id, "Op")
    with (
        lobby.websocket_connect(f"/ws/match/{match_id}?token={token_x}") as wx,
        lobby.websocket_connect(f"/ws/match/{match_id}?token={token_o}") as wo,
    ):
        wx.receive_json()  # joined X
        wo.receive_json()  # joined O
        # X wins the top row: X0, O3, X1, O4, then X2.
        for ws, player, cell in [(wx, "X", 0), (wo, "O", 3), (wx, "X", 1), (wo, "O", 4)]:
            _submit(ws, cell)
            update = wx.receive_json()
            wo.receive_json()
            assert update["event"] == "state_update"
            assert update["payload"]["last_move"] == {"player": player, "move": cell}
            assert update["payload"]["current_turn"] is not None
        _submit(wx, 2)  # winning move
        terminal = wx.receive_json()
        wo.receive_json()
        assert terminal["event"] == "state_update"
        assert terminal["payload"]["current_turn"] is None  # null on the game-ending move
        assert terminal["payload"]["valid_moves"] == []
        over_x = wx.receive_json()
        over_o = wo.receive_json()
        assert over_x == {"event": "game_over", "payload": {"result": "X"}}
        assert over_o == {"event": "game_over", "payload": {"result": "X"}}

    assert _match_row(tmp_path, match_id) == ("finished", "X")


def test_full_game_draw(lobby: TestClient, tmp_path: Path) -> None:
    match_id = _match(lobby)
    token_x = _join(lobby, match_id, "Xp")
    token_o = _join(lobby, match_id, "Op")
    with (
        lobby.websocket_connect(f"/ws/match/{match_id}?token={token_x}") as wx,
        lobby.websocket_connect(f"/ws/match/{match_id}?token={token_o}") as wo,
    ):
        wx.receive_json()
        wo.receive_json()
        # Draw board: X O X / X O O / O X X
        for ws, cell in [(wx, 0), (wo, 1), (wx, 2), (wo, 4), (wx, 3), (wo, 5), (wx, 7), (wo, 6)]:
            _submit(ws, cell)
            wx.receive_json()
            wo.receive_json()
        _submit(wx, 8)  # final move -> draw
        terminal = wx.receive_json()
        wo.receive_json()
        assert terminal["payload"]["current_turn"] is None
        over = wx.receive_json()
        wo.receive_json()
        assert over == {"event": "game_over", "payload": {"result": "draw"}}

    assert _match_row(tmp_path, match_id) == ("finished", "draw")


def test_out_of_turn_move_rejected(lobby: TestClient) -> None:
    match_id = _match(lobby)
    token_x = _join(lobby, match_id, "Xp")
    token_o = _join(lobby, match_id, "Op")
    with (
        lobby.websocket_connect(f"/ws/match/{match_id}?token={token_x}") as wx,
        lobby.websocket_connect(f"/ws/match/{match_id}?token={token_o}") as wo,
    ):
        wx.receive_json()
        wo.receive_json()
        _submit(wo, 0)  # O moves first — but it is X's turn
        err = wo.receive_json()
        assert err["event"] == "error"
        assert "turn" in err["payload"]["detail"]


def test_illegal_move_rejected(lobby: TestClient) -> None:
    match_id = _match(lobby)
    token_x = _join(lobby, match_id, "Xp")
    token_o = _join(lobby, match_id, "Op")
    with (
        lobby.websocket_connect(f"/ws/match/{match_id}?token={token_x}") as wx,
        lobby.websocket_connect(f"/ws/match/{match_id}?token={token_o}") as wo,
    ):
        wx.receive_json()
        wo.receive_json()
        _submit(wx, 0)  # X takes cell 0
        wx.receive_json()
        wo.receive_json()
        _submit(wo, 0)  # O tries the occupied cell 0
        err = wo.receive_json()
        assert err["event"] == "error"
        assert "invalid" in err["payload"]["detail"]


def test_no_seat_spectator_move_rejected(lobby: TestClient) -> None:
    match_id = _match(lobby)
    observer = _join(lobby, match_id, "Watcher", spectator=True)
    with lobby.websocket_connect(f"/ws/match/{match_id}?token={observer}") as ws:
        ws.receive_json()  # joined with symbol null
        _submit(ws, 0)
        err = ws.receive_json()
        assert err["event"] == "error"
        assert "seat" in err["payload"]["detail"]
