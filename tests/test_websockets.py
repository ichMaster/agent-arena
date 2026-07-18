from server.websockets import ClientActionPayload, ConnectionManager, ServerPushEvent


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
