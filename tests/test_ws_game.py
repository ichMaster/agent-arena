"""submit_move authority flow + game_over (ARENA-OPUS-OPUS-015). Two real WS connections, throwaway
DB; no LLM, no paid call. The v01 release gate: full server-validated games + all rejections.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.database import create_engine, create_session_maker
from server.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/game.db")
    app = create_app(db_engine=engine, session_maker=create_session_maker(engine))
    with TestClient(app) as c:
        yield c


def _join(client: TestClient, match_id: str, name: str, spectator: bool = False) -> str:
    body = {"match_id": match_id, "player_name": name, "spectator": spectator}
    return str(client.post("/api/v1/lobby/join", json=body).json()["token"])


def _open_two(client: TestClient) -> tuple[str, str, str]:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    return match_id, _join(client, match_id, "X"), _join(client, match_id, "O")


def test_full_game_x_wins(client: TestClient) -> None:
    match_id, tx, to = _open_two(client)
    with client.websocket_connect(f"/ws/match/{match_id}?token={tx}") as wx, \
         client.websocket_connect(f"/ws/match/{match_id}?token={to}") as wo:
        wx.receive_json()
        wo.receive_json()
        # X: 0,1,2 (top row); O: 3,4.
        moves = [(wx, 0), (wo, 3), (wx, 1), (wo, 4), (wx, 2)]
        for i, (sock, cell) in enumerate(moves):
            sock.send_json({"action": "submit_move", "payload": {"move": cell}})
            su_x = wx.receive_json()
            su_o = wo.receive_json()
            assert su_x == su_o and su_x["event"] == "state_update"
            if i == len(moves) - 1:  # the winning move
                assert su_x["payload"]["current_turn"] is None
                over_x = wx.receive_json()
                over_o = wo.receive_json()
                assert over_x == over_o == {"event": "game_over", "payload": {"result": "X"}}


def test_full_game_draw(client: TestClient) -> None:
    match_id, tx, to = _open_two(client)
    with client.websocket_connect(f"/ws/match/{match_id}?token={tx}") as wx, \
         client.websocket_connect(f"/ws/match/{match_id}?token={to}") as wo:
        wx.receive_json()
        wo.receive_json()
        # X O X / X O O / O X X -> full, no line.
        seq = [(wx, 0), (wo, 1), (wx, 2), (wo, 4), (wx, 3), (wo, 5), (wx, 7), (wo, 6), (wx, 8)]
        result = None
        for sock, cell in seq:
            sock.send_json({"action": "submit_move", "payload": {"move": cell}})
            wx.receive_json()
            su = wo.receive_json()
            if su["payload"]["current_turn"] is None:
                over = wx.receive_json()
                wo.receive_json()
                result = over["payload"]["result"]
        assert result == "draw"


def test_out_of_turn_rejected(client: TestClient) -> None:
    match_id, tx, to = _open_two(client)
    with client.websocket_connect(f"/ws/match/{match_id}?token={tx}") as wx, \
         client.websocket_connect(f"/ws/match/{match_id}?token={to}") as wo:
        wx.receive_json()
        wo.receive_json()
        wo.send_json({"action": "submit_move", "payload": {"move": 0}})  # O tries first
        assert wo.receive_json() == {"event": "error", "payload": {"detail": "not your turn"}}


def test_illegal_move_rejected(client: TestClient) -> None:
    match_id, tx, to = _open_two(client)
    with client.websocket_connect(f"/ws/match/{match_id}?token={tx}") as wx, \
         client.websocket_connect(f"/ws/match/{match_id}?token={to}") as wo:
        wx.receive_json()
        wo.receive_json()
        wx.send_json({"action": "submit_move", "payload": {"move": 99}})  # out of range
        assert wx.receive_json() == {"event": "error", "payload": {"detail": "invalid move"}}


def test_no_seat_observer_move_rejected(client: TestClient) -> None:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    _join(client, match_id, "X")
    _join(client, match_id, "O")
    obs = _join(client, match_id, "Watcher", spectator=True)
    with client.websocket_connect(f"/ws/match/{match_id}?token={obs}") as ws:
        ws.receive_json()  # joined (symbol null)
        ws.send_json({"action": "submit_move", "payload": {"move": 0}})
        assert ws.receive_json() == {"event": "error", "payload": {"detail": "no seat"}}
