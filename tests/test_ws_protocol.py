"""Contract + unit tests for the WS protocol layer (architecture §5.3, §6.2).

Pins every server->client event shape and the client->server action envelope, and exercises the
ConnectionManager with fake WebSocket doubles. No DB, no LLM, no paid call.
"""

from typing import Any

from server.websockets import (
    ConnectionManager,
    chat_message_event,
    error_event,
    game_over_event,
    joined_event,
    parse_action,
    state_update_event,
)


class FakeWebSocket:
    """A minimal WebSocket double: records accept/send/close; can simulate a dead send."""

    def __init__(self, fail_send: bool = False) -> None:
        self.accepted = False
        self.closed = False
        self.sent: list[str] = []
        self._fail_send = fail_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        if self._fail_send:
            raise RuntimeError("dead socket")
        self.sent.append(data)

    async def close(self, code: int = 1000) -> None:
        self.closed = True


# --- Contract: event/action shapes (§6.2) -----------------------------------


def test_joined_event_shape() -> None:
    assert joined_event("X", ["", ""], "X", [0, 1]) == {
        "event": "joined",
        "payload": {"symbol": "X", "board": ["", ""], "current_turn": "X", "valid_moves": [0, 1]},
    }


def test_joined_event_observer_symbol_null() -> None:
    assert joined_event(None, [], None, [])["payload"]["symbol"] is None


def test_state_update_event_shape() -> None:
    evt = state_update_event(["X"], None, [], {"player": "X", "move": 0})
    assert evt["event"] == "state_update"
    assert set(evt["payload"]) == {"board", "current_turn", "valid_moves", "last_move"}
    assert evt["payload"]["current_turn"] is None
    assert evt["payload"]["last_move"] == {"player": "X", "move": 0}


def test_chat_message_event_shape() -> None:
    assert chat_message_event("O", "gg") == {
        "event": "chat_message",
        "payload": {"sender": "O", "message": "gg"},
    }


def test_game_over_event_shape() -> None:
    assert game_over_event("draw") == {"event": "game_over", "payload": {"result": "draw"}}


def test_error_event_shape() -> None:
    assert error_event("not your turn") == {
        "event": "error",
        "payload": {"detail": "not your turn"},
    }


def test_parse_action_valid() -> None:
    assert parse_action({"action": "submit_move", "payload": {"move": 4}}) == (
        "submit_move",
        {"move": 4},
    )


def test_parse_action_missing_or_malformed() -> None:
    assert parse_action({}) == (None, {})
    assert parse_action({"action": 5, "payload": "nope"}) == (None, {})


# --- Unit: ConnectionManager (§5.3) -----------------------------------------


async def test_connect_registers_and_accepts() -> None:
    manager = ConnectionManager()
    socket = FakeWebSocket()
    await manager.connect("m", socket, "t1")  # type: ignore[arg-type]
    assert socket.accepted
    assert manager.connection_count("m") == 1


async def test_broadcast_serializes_once_to_all() -> None:
    manager = ConnectionManager()
    a, b = FakeWebSocket(), FakeWebSocket()
    await manager.connect("m", a, "t1")  # type: ignore[arg-type]
    await manager.connect("m", b, "t2")  # type: ignore[arg-type]
    await manager.broadcast("m", error_event("hi"))
    assert len(a.sent) == 1 and len(b.sent) == 1
    assert a.sent[0] == b.sent[0]  # serialized once, same payload


async def test_broadcast_prunes_dead_socket_and_delivers_to_rest() -> None:
    manager = ConnectionManager()
    good, dead = FakeWebSocket(), FakeWebSocket(fail_send=True)
    await manager.connect("m", good, "t1")  # type: ignore[arg-type]
    await manager.connect("m", dead, "t2")  # type: ignore[arg-type]
    await manager.broadcast("m", error_event("x"))
    assert len(good.sent) == 1  # healthy socket still received
    assert manager.connection_count("m") == 1  # dead one pruned


async def test_disconnect_returns_owner_and_is_idempotent() -> None:
    manager = ConnectionManager()
    socket = FakeWebSocket()
    await manager.connect("m", socket, "t1")  # type: ignore[arg-type]
    assert manager.disconnect("m", socket) == "t1"  # type: ignore[arg-type]
    assert manager.connection_count("m") == 0
    assert manager.disconnect("m", socket) is None  # type: ignore[arg-type]


async def test_close_room_closes_all_sockets() -> None:
    manager = ConnectionManager()
    a, b = FakeWebSocket(), FakeWebSocket()
    await manager.connect("m", a, "t1")  # type: ignore[arg-type]
    await manager.connect("m", b, "t2")  # type: ignore[arg-type]
    await manager.close_room("m")
    assert a.closed and b.closed
    assert manager.connection_count("m") == 0


async def test_send_to_single_socket() -> None:
    manager = ConnectionManager()
    socket = FakeWebSocket()
    await manager.connect("m", socket, "t1")  # type: ignore[arg-type]
    await manager.send_to(socket, chat_message_event("X", "hi"))  # type: ignore[arg-type]
    assert len(socket.sent) == 1
