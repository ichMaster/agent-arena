import time
import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.main import app
from server.websockets import manager


def _wait_until(predicate: Callable[[], bool], timeout: float = 2.0) -> None:
    """TestClient's WS `with` block exit sends a close frame but doesn't
    guarantee the server's WebSocketDisconnect handler (running in the
    TestClient's background portal thread) has finished before returning —
    poll instead of assuming that cleanup already happened synchronously."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError(f"condition not met within {timeout}s")

# Entered (not `with`-scoped) so the FastAPI lifespan runs once and the DB schema
# exists for every test function below, which share this single client instance.
client = TestClient(app)
client.__enter__()


def _create_match() -> str:
    return str(client.post("/api/v1/lobby/match").json()["match_id"])


def _join(match_id: str, player_name: str = "Ada") -> str:
    response = client.post("/api/v1/lobby/join", json={"match_id": match_id, "player_name": player_name})
    return response.json()["token"]


def _drain_joined(websocket) -> dict:
    """Every WS connection gets a one-time "joined" event (assigned symbol +
    current board) immediately after accept, before anything else. Tests that
    care about subsequent messages must consume it first."""
    event = websocket.receive_json()
    assert event["event"] == "joined"
    return event


def test_health_returns_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_match_returns_valid_uuid() -> None:
    response = client.post("/api/v1/lobby/match")
    assert response.status_code == 200
    body = response.json()
    assert "match_id" in body
    assert uuid.UUID(body["match_id"]).version == 4


def test_join_match_returns_token() -> None:
    match_id = _create_match()
    response = client.post("/api/v1/lobby/join", json={"match_id": match_id, "player_name": "Ada"})
    assert response.status_code == 200
    assert "token" in response.json()


def test_join_match_rejects_unknown_match_id() -> None:
    response = client.post(
        "/api/v1/lobby/join", json={"match_id": str(uuid.uuid4()), "player_name": "Ada"}
    )
    assert response.status_code == 404


def test_join_match_rejects_missing_fields() -> None:
    response = client.post("/api/v1/lobby/join", json={"match_id": str(uuid.uuid4())})
    assert response.status_code == 422


def test_ws_connect_with_valid_token_is_accepted() -> None:
    match_id = _create_match()
    token = _join(match_id)
    with client.websocket_connect(f"/ws/match/{match_id}?token={token}") as websocket:
        assert websocket is not None


def test_ws_connect_without_token_is_closed() -> None:
    match_id = str(uuid.uuid4())
    try:
        with client.websocket_connect(f"/ws/match/{match_id}"):
            raise AssertionError("connection should have been closed before accept")
    except WebSocketDisconnect as exc:
        assert exc.code == 4001


def test_ws_connect_with_invalid_token_is_closed() -> None:
    match_id = str(uuid.uuid4())
    try:
        with client.websocket_connect(f"/ws/match/{match_id}?token=not-a-real-token"):
            raise AssertionError("connection should have been closed before accept")
    except WebSocketDisconnect as exc:
        assert exc.code == 4001


def test_ws_connect_with_token_for_different_match_is_closed() -> None:
    joined_match_id = _create_match()
    other_match_id = _create_match()
    token = _join(joined_match_id)
    try:
        with client.websocket_connect(f"/ws/match/{other_match_id}?token={token}"):
            raise AssertionError("connection should have been closed before accept")
    except WebSocketDisconnect as exc:
        assert exc.code == 4001


def test_ws_chat_action_is_broadcast_to_room() -> None:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    token = _join(match_id, "Ada")

    with client.websocket_connect(f"/ws/match/{match_id}?token={token}") as websocket:
        _drain_joined(websocket)
        websocket.send_json({"action": "chat", "payload": {"message": "hello room"}})
        event = websocket.receive_json()
        assert event == {"event": "chat_message", "payload": {"sender": "Ada", "message": "hello room"}}


def test_ws_two_concurrent_clients_exchange_chat_in_same_match() -> None:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    ada_token = _join(match_id, "Ada")
    bob_token = _join(match_id, "Bob")

    with (
        client.websocket_connect(f"/ws/match/{match_id}?token={ada_token}") as ada_ws,
        client.websocket_connect(f"/ws/match/{match_id}?token={bob_token}") as bob_ws,
    ):
        _drain_joined(ada_ws)
        _drain_joined(bob_ws)

        ada_ws.send_json({"action": "chat", "payload": {"message": "hi from Ada"}})
        assert ada_ws.receive_json() == {
            "event": "chat_message",
            "payload": {"sender": "Ada", "message": "hi from Ada"},
        }
        assert bob_ws.receive_json() == {
            "event": "chat_message",
            "payload": {"sender": "Ada", "message": "hi from Ada"},
        }

        bob_ws.send_json({"action": "chat", "payload": {"message": "hi from Bob"}})
        assert ada_ws.receive_json() == {
            "event": "chat_message",
            "payload": {"sender": "Bob", "message": "hi from Bob"},
        }
        assert bob_ws.receive_json() == {
            "event": "chat_message",
            "payload": {"sender": "Bob", "message": "hi from Bob"},
        }


def test_ws_clients_in_different_matches_do_not_cross_talk() -> None:
    match_a = client.post("/api/v1/lobby/match").json()["match_id"]
    match_b = client.post("/api/v1/lobby/match").json()["match_id"]
    token_a = _join(match_a, "Ada")
    token_b = _join(match_b, "Bob")

    with (
        client.websocket_connect(f"/ws/match/{match_a}?token={token_a}") as ws_a,
        client.websocket_connect(f"/ws/match/{match_b}?token={token_b}") as ws_b,
    ):
        _drain_joined(ws_a)
        _drain_joined(ws_b)

        ws_a.send_json({"action": "chat", "payload": {"message": "only for match A"}})
        assert ws_a.receive_json()["payload"]["message"] == "only for match A"

        ws_b.send_json({"action": "chat", "payload": {"message": "ping"}})
        assert ws_b.receive_json()["payload"]["message"] == "ping"
        # ws_b should never have received match A's message; if it had, it would
        # have been consumed by the receive_json() call above instead of "ping".


def test_ws_malformed_json_gets_error_reply_without_crashing() -> None:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    token = _join(match_id, "Ada")

    with client.websocket_connect(f"/ws/match/{match_id}?token={token}") as websocket:
        _drain_joined(websocket)
        websocket.send_text("not valid json")
        event = websocket.receive_json()
        assert event["event"] == "error"

        # connection is still alive and the loop is still running
        websocket.send_json({"action": "chat", "payload": {"message": "still here"}})
        event = websocket.receive_json()
        assert event["event"] == "chat_message"


def test_ws_two_players_complete_full_tictactoe_game() -> None:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    ada_token = _join(match_id, "Ada")
    bob_token = _join(match_id, "Bob")

    with (
        client.websocket_connect(f"/ws/match/{match_id}?token={ada_token}") as ada_ws,
        client.websocket_connect(f"/ws/match/{match_id}?token={bob_token}") as bob_ws,
    ):
        # Ada connects first and is assigned X; Bob is assigned O. X wins the top row (0,1,2).
        assert _drain_joined(ada_ws)["payload"]["symbol"] == "X"
        assert _drain_joined(bob_ws)["payload"]["symbol"] == "O"

        sequence = [(ada_ws, 0), (bob_ws, 3), (ada_ws, 1), (bob_ws, 4), (ada_ws, 2)]
        for sender_ws, move in sequence:
            sender_ws.send_json({"action": "submit_move", "payload": {"move": move}})
            for ws in (ada_ws, bob_ws):
                update = ws.receive_json()
                assert update["event"] == "state_update"
                assert update["payload"]["board"][move] in ("X", "O")

        for ws in (ada_ws, bob_ws):
            game_over = ws.receive_json()
            assert game_over == {"event": "game_over", "payload": {"result": "X"}}

    assert manager.connection_count(match_id) == 0


def test_ws_invalid_move_is_isolated_and_does_not_crash_server() -> None:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    ada_token = _join(match_id, "Ada")
    bob_token = _join(match_id, "Bob")

    with (
        client.websocket_connect(f"/ws/match/{match_id}?token={ada_token}") as ada_ws,
        client.websocket_connect(f"/ws/match/{match_id}?token={bob_token}") as bob_ws,
    ):
        # Ada connects first and is assigned X; she plays a valid opening move.
        _drain_joined(ada_ws)
        _drain_joined(bob_ws)
        ada_ws.send_json({"action": "submit_move", "payload": {"move": 0}})
        ada_ws.receive_json()
        bob_ws.receive_json()

        # It's now O's turn, but Ada (X) tries to move again — rejected, and only
        # Ada sees the error; Bob's connection receives nothing for it.
        ada_ws.send_json({"action": "submit_move", "payload": {"move": 1}})
        error = ada_ws.receive_json()
        assert error["event"] == "error"
        assert "turn" in error["payload"]["detail"].lower()

        # The server is still healthy: Bob (O) can now play normally, and both
        # participants receive the same broadcast (no crash, no phantom state).
        bob_ws.send_json({"action": "submit_move", "payload": {"move": 3}})
        ada_update = ada_ws.receive_json()
        bob_update = bob_ws.receive_json()
        assert ada_update == bob_update
        assert ada_update["event"] == "state_update"
        assert ada_update["payload"]["board"][3] == "O"


def test_ws_two_sessions_with_the_same_display_name_get_different_seats() -> None:
    """Regression: the Web UI defaults every session's name prompt to
    "Human" (web/app.js). Two different people who both accept that default
    and join the same match must not end up sharing a seat."""
    match_id = _create_match()
    token_1 = _join(match_id, "Human")
    token_2 = _join(match_id, "Human")

    with (
        client.websocket_connect(f"/ws/match/{match_id}?token={token_1}") as ws_1,
        client.websocket_connect(f"/ws/match/{match_id}?token={token_2}") as ws_2,
    ):
        symbol_1 = _drain_joined(ws_1)["payload"]["symbol"]
        symbol_2 = _drain_joined(ws_2)["payload"]["symbol"]

    assert symbol_1 != symbol_2
    assert {symbol_1, symbol_2} == {"X", "O"}


def test_ws_disconnect_frees_the_seat_for_a_new_participant() -> None:
    """Regression: a mid-game disconnect must not permanently strand the
    match — a new participant should be able to take the vacated seat, even
    while the OTHER original participant stays connected throughout."""
    match_id = _create_match()
    ada_token = _join(match_id, "Ada")
    bob_token = _join(match_id, "Bob")

    with client.websocket_connect(f"/ws/match/{match_id}?token={bob_token}") as bob_ws:
        with client.websocket_connect(f"/ws/match/{match_id}?token={ada_token}") as ada_ws:
            assert _drain_joined(bob_ws)["payload"]["symbol"] == "X"
            assert _drain_joined(ada_ws)["payload"]["symbol"] == "O"
        # Ada's connection is now closed (inner `with` block exited); Bob's
        # stays open. Wait for the server to actually finish processing
        # Ada's disconnect before Cara tries to take her seat.
        _wait_until(lambda: manager.connection_count(match_id) == 1)

        # Before the fix, a third participant would always be rejected (None)
        # since Ada's old seat was never released. Now it should be reclaimed
        # — and Bob, still connected, must be unaffected (still O).
        cara_token = _join(match_id, "Cara")
        with client.websocket_connect(f"/ws/match/{match_id}?token={cara_token}") as cara_ws:
            assert _drain_joined(cara_ws)["payload"]["symbol"] == "O"
