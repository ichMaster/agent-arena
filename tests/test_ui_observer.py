"""Observer role — served-asset wiring + an end-to-end seat-less watch (ARENA-OPUS-031, v03 gate).

The observer path is proven against the REAL server: a spectator gets symbol:null and no seat, and
forced actions are refused server-side (the UI suppresses them, but the server is the guard, §5). No LLM.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.database import create_engine, create_session_maker
from server.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/obs.db")
    app = create_app(db_engine=engine, session_maker=create_session_maker(engine))
    with TestClient(app) as c:
        yield c


def _join(client: TestClient, match_id: str, name: str, spectator: bool = False) -> str:
    body = {"match_id": match_id, "player_name": name, "spectator": spectator}
    return str(client.post("/api/v1/lobby/join", json=body).json()["token"])


# --- served-asset wiring ---

def test_spectate_sends_spectator_true_distinct_from_join(client: TestClient) -> None:
    js = client.get("/ui/app.js").text
    assert "joinAndConnect(id, true)" in js   # spectateMatch
    assert "joinAndConnect(id, false)" in js  # joinMatch (Player)
    # role labelled Observer when symbol is null; chat gated by role
    assert "'Observer'" in js
    assert "setChatEnabled(mySymbol !== null)" in js


# --- end-to-end against the real server ---

def test_observer_gets_null_symbol_no_seat_and_is_refused(client: TestClient) -> None:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    x_token = _join(client, match_id, "Blaze-X")
    obs_token = _join(client, match_id, "Watcher", spectator=True)

    with client.websocket_connect(f"/ws/match/{match_id}?token={x_token}") as wx:
        assert wx.receive_json()["payload"]["symbol"] == "X"  # a seated player, stays connected

        with client.websocket_connect(f"/ws/match/{match_id}?token={obs_token}") as wo:
            joined = wo.receive_json()
            assert joined["event"] == "joined"
            assert joined["payload"]["symbol"] is None       # Observer: no seat

            wo.send_json({"action": "submit_move", "payload": {"move": 0}})
            assert wo.receive_json() == {"event": "error", "payload": {"detail": "no seat"}}

            wo.send_json({"action": "chat", "payload": {"message": "let me in"}})
            err = wo.receive_json()
            assert err["event"] == "error" and "observers cannot chat" in err["payload"]["detail"]

        # With X still connected, the observer left no footprint: O is still free for a real player.
        o_token = _join(client, match_id, "Blaze-O")
        with client.websocket_connect(f"/ws/match/{match_id}?token={o_token}") as wo2:
            assert wo2.receive_json()["payload"]["symbol"] == "O"


def test_host_and_join_default_to_player(client: TestClient) -> None:
    js = client.get("/ui/app.js").text
    # hostMatch joins non-spectator; joinMatch too
    host_idx = js.index("async function hostMatch")
    assert "joinAndConnect(created.match_id, false)" in js[host_idx:host_idx + 300]
