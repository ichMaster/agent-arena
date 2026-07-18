import uuid

from server.repository import Repository
from server.websockets import ClientActionPayload, ConnectionManager, ServerPushEvent, handle_client_message
from server.websockets import manager as global_manager


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)


async def test_connect_tracks_connection_count() -> None:
    manager = ConnectionManager()
    ws = FakeWebSocket()
    await manager.connect("match-1", ws)
    assert ws.accepted is True
    assert manager.connection_count("match-1") == 1


async def test_disconnect_removes_connection() -> None:
    manager = ConnectionManager()
    ws = FakeWebSocket()
    await manager.connect("match-1", ws)
    manager.disconnect("match-1", ws)
    assert manager.connection_count("match-1") == 0


async def test_broadcast_sends_to_all_connections_in_match() -> None:
    manager = ConnectionManager()
    ws1, ws2, ws_other_match = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()
    await manager.connect("match-1", ws1)
    await manager.connect("match-1", ws2)
    await manager.connect("match-2", ws_other_match)

    await manager.broadcast("match-1", ServerPushEvent(event="chat_message", payload={"text": "hi"}))

    assert ws1.sent == [{"event": "chat_message", "payload": {"text": "hi"}}]
    assert ws2.sent == [{"event": "chat_message", "payload": {"text": "hi"}}]
    assert ws_other_match.sent == []


def test_client_action_payload_defaults_empty_payload() -> None:
    action = ClientActionPayload(action="chat")
    assert action.payload == {}


async def test_handle_client_message_persists_and_broadcasts_chat(repository: Repository) -> None:
    match_id = str(uuid.uuid4())
    await repository.create_match(match_id)
    ws = FakeWebSocket()
    await global_manager.connect(match_id, ws)
    try:
        reply = await handle_client_message(
            repository, match_id, "Ada", {"action": "chat", "payload": {"message": "hello"}}
        )
        assert reply is None
        assert ws.sent == [{"event": "chat_message", "payload": {"sender": "Ada", "message": "hello"}}]
        logs = await repository.get_chat_logs(match_id)
        assert len(logs) == 1
        assert logs[0].message == "hello"
    finally:
        global_manager.disconnect(match_id, ws)


async def test_handle_client_message_returns_error_for_unknown_action(repository: Repository) -> None:
    match_id = str(uuid.uuid4())
    await repository.create_match(match_id)
    reply = await handle_client_message(repository, match_id, "Ada", {"action": "teleport"})
    assert reply is not None
    assert reply.event == "error"


async def test_handle_client_message_returns_error_for_invalid_schema(repository: Repository) -> None:
    reply = await handle_client_message(repository, "match-x", "Ada", {"payload": {}})
    assert reply is not None
    assert reply.event == "error"
