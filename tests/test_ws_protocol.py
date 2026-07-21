"""Protocol-layer tests (ARENA-OPUS-OPUS-012): pinned event/action shapes + ConnectionManager
behavior with fake sockets. No DB, no LLM, no paid call.
"""

from typing import Any

import pytest

from server.websockets import (
    ConnectionManager,
    chat_message_event,
    error_event,
    game_over_event,
    joined_event,
    parse_action,
    state_update_event,
)


# --- Pinned wire shapes (§6.2) ---
def test_joined_event_shape() -> None:
    assert joined_event("X", [""] * 9, "X", [0, 1]) == {
        "event": "joined",
        "payload": {"symbol": "X", "board": [""] * 9, "current_turn": "X", "valid_moves": [0, 1]},
    }


def test_state_update_shape_with_null_turn() -> None:
    ev = state_update_event(["X"] * 3 + [""] * 6, None, [], {"player": "X", "move": 2})
    assert ev["event"] == "state_update"
    assert ev["payload"]["current_turn"] is None
    assert ev["payload"]["last_move"] == {"player": "X", "move": 2}


def test_chat_and_game_over_and_error_shapes() -> None:
    assert chat_message_event("X", "hi") == {
        "event": "chat_message",
        "payload": {"sender": "X", "message": "hi"},
    }
    assert game_over_event("draw") == {"event": "game_over", "payload": {"result": "draw"}}
    assert error_event("no seat") == {"event": "error", "payload": {"detail": "no seat"}}


@pytest.mark.parametrize(
    "message,expected",
    [
        ({"action": "chat", "payload": {"message": "hi"}}, ("chat", {"message": "hi"})),
        ({"action": "submit_move", "payload": {"move": 4}}, ("submit_move", {"move": 4})),
        ({"action": 123, "payload": {}}, (None, {})),  # non-str action
        ({"payload": {}}, (None, {})),  # missing action
        ({"action": "chat"}, ("chat", {})),  # missing payload
    ],
)
def test_parse_action(message: dict[str, Any], expected: tuple[str | None, dict[str, Any]]) -> None:
    assert parse_action(message) == expected


# --- ConnectionManager with fake sockets ---
class FakeWebSocket:
    def __init__(self, fail_on_send: bool = False) -> None:
        self.sent: list[str] = []
        self.closed = False
        self.accepted = False
        self._fail = fail_on_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, text: str) -> None:
        if self._fail:
            raise RuntimeError("dead socket")
        self.sent.append(text)

    async def close(self) -> None:
        self.closed = True


async def test_connect_registers_and_disconnect_returns_owner() -> None:
    mgr = ConnectionManager()
    ws = FakeWebSocket()
    await mgr.connect("m1", ws, "tok-1")  # type: ignore[arg-type]
    assert ws.accepted
    assert mgr.disconnect("m1", ws) == "tok-1"  # type: ignore[arg-type]
    assert mgr.disconnect("m1", ws) is None  # idempotent


async def test_broadcast_serializes_once_and_prunes_dead_socket() -> None:
    mgr = ConnectionManager()
    good, dead = FakeWebSocket(), FakeWebSocket(fail_on_send=True)
    await mgr.connect("m1", good, "t1")  # type: ignore[arg-type]
    await mgr.connect("m1", dead, "t2")  # type: ignore[arg-type]
    await mgr.broadcast("m1", {"event": "x", "payload": {}})
    assert len(good.sent) == 1  # healthy socket got it
    assert mgr.disconnect("m1", dead) is None  # dead one was pruned already


async def test_close_room_closes_all() -> None:
    mgr = ConnectionManager()
    a, b = FakeWebSocket(), FakeWebSocket()
    await mgr.connect("m1", a, "t1")  # type: ignore[arg-type]
    await mgr.connect("m1", b, "t2")  # type: ignore[arg-type]
    await mgr.close_room("m1")
    assert a.closed and b.closed
    assert mgr.disconnect("m1", a) is None
