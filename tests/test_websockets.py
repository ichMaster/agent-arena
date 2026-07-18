import uuid

from server.match import clear_match
from server.repository import Repository
from server.websockets import ClientActionPayload, ConnectionManager, ServerPushEvent, handle_client_message
from server.websockets import manager as global_manager


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self.closed = False
        self.close_code: int | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000) -> None:
        self.closed = True
        self.close_code = code


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


async def test_submit_move_valid_updates_state_and_broadcasts(repository: Repository) -> None:
    match_id = str(uuid.uuid4())
    await repository.create_match(match_id)
    ws = FakeWebSocket()
    await global_manager.connect(match_id, ws)
    try:
        reply = await handle_client_message(
            repository, match_id, "Ada", {"action": "submit_move", "payload": {"move": 4}}
        )
        assert reply is None
        update = ws.sent[-1]
        assert update["event"] == "state_update"
        assert update["payload"]["board"][4] == "X"
        assert update["payload"]["current_turn"] == "O"
        assert 4 not in update["payload"]["valid_moves"]

        moves = await repository.get_move_logs(match_id)
        assert len(moves) == 1
        assert moves[0].player_id == "X"
    finally:
        global_manager.disconnect(match_id, ws)
        clear_match(match_id)


async def test_submit_move_out_of_turn_is_rejected(repository: Repository) -> None:
    match_id = str(uuid.uuid4())
    await repository.create_match(match_id)
    try:
        await handle_client_message(repository, match_id, "Ada", {"action": "submit_move", "payload": {"move": 0}})
        reply = await handle_client_message(
            repository, match_id, "Ada", {"action": "submit_move", "payload": {"move": 1}}
        )
        assert reply is not None
        assert reply.event == "error"
        assert "turn" in reply.payload["detail"].lower()
    finally:
        clear_match(match_id)


async def test_submit_move_invalid_cell_is_rejected(repository: Repository) -> None:
    match_id = str(uuid.uuid4())
    await repository.create_match(match_id)
    try:
        reply = await handle_client_message(
            repository, match_id, "Ada", {"action": "submit_move", "payload": {"move": 99}}
        )
        assert reply is not None
        assert reply.event == "error"
    finally:
        clear_match(match_id)


async def test_third_player_gets_no_seat(repository: Repository) -> None:
    match_id = str(uuid.uuid4())
    await repository.create_match(match_id)
    try:
        await handle_client_message(repository, match_id, "Ada", {"action": "submit_move", "payload": {"move": 0}})
        await handle_client_message(repository, match_id, "Bob", {"action": "submit_move", "payload": {"move": 1}})
        reply = await handle_client_message(
            repository, match_id, "Cara", {"action": "submit_move", "payload": {"move": 2}}
        )
        assert reply is not None
        assert reply.event == "error"
    finally:
        clear_match(match_id)


async def test_winning_move_broadcasts_game_over_and_closes_room(repository: Repository) -> None:
    match_id = str(uuid.uuid4())
    await repository.create_match(match_id)
    ws_x, ws_o = FakeWebSocket(), FakeWebSocket()
    await global_manager.connect(match_id, ws_x)
    await global_manager.connect(match_id, ws_o)
    try:
        # X plays the top row (0,1,2); O plays elsewhere (3,4).
        for sender, move in [("Ada", 0), ("Bob", 3), ("Ada", 1), ("Bob", 4), ("Ada", 2)]:
            await handle_client_message(repository, match_id, sender, {"action": "submit_move", "payload": {"move": move}})

        assert ws_x.sent[-1] == {"event": "game_over", "payload": {"result": "X"}}
        assert ws_o.sent[-1] == {"event": "game_over", "payload": {"result": "X"}}
        assert ws_x.closed is True
        assert ws_o.closed is True
        assert global_manager.connection_count(match_id) == 0
    finally:
        clear_match(match_id)
