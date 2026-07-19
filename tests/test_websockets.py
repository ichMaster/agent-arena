import uuid

from server.match import clear_match, get_or_create_match
from server.repository import Repository
from server.websockets import ClientActionPayload, ConnectionManager, ServerPushEvent, handle_client_message
from server.websockets import manager as global_manager


class FakeWebSocket:
    def __init__(self, fail_send: bool = False) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self.closed = False
        self.close_code: int | None = None
        self.fail_send = fail_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict) -> None:
        if self.fail_send:
            raise RuntimeError("connection reset by peer")
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


async def test_connect_tracks_owner_and_disconnect_releases_the_seat() -> None:
    """Proves the full wiring: ConnectionManager.connect(participant_id=...)
    tracks the owner, and disconnect() looks it up and calls into the real
    active-match registry (server.match) to free that seat — not just a
    locally-constructed Match no one else can see."""
    match_id = str(uuid.uuid4())
    match = get_or_create_match(match_id)
    manager = ConnectionManager()
    ws = FakeWebSocket()

    await manager.connect(match_id, ws, participant_id="token-ada")
    assert match.assign_symbol("token-ada") == "X"  # seat taken
    try:
        assert match.assign_symbol("token-bob") == "O"
        assert match.assign_symbol("token-cara") is None  # no seats left

        manager.disconnect(match_id, ws)

        assert match.assign_symbol("token-cara") == "X"  # Ada's seat reclaimed
    finally:
        clear_match(match_id)


async def test_connect_without_participant_id_does_not_track_an_owner() -> None:
    manager = ConnectionManager()
    ws = FakeWebSocket()
    await manager.connect("match-1", ws)  # no participant_id — e.g. legacy/spectator usage
    manager.disconnect("match-1", ws)  # must not raise even though nothing was tracked
    assert manager.connection_count("match-1") == 0


async def test_broadcast_skips_a_dead_socket_without_crashing_and_still_reaches_others() -> None:
    manager = ConnectionManager()
    dead_ws = FakeWebSocket(fail_send=True)
    live_ws = FakeWebSocket()
    await manager.connect("match-1", dead_ws)
    await manager.connect("match-1", live_ws)

    # Must not raise, even though dead_ws.send_json always raises.
    await manager.broadcast("match-1", ServerPushEvent(event="chat_message", payload={"text": "hi"}))

    assert live_ws.sent == [{"event": "chat_message", "payload": {"text": "hi"}}]
    # The dead socket was removed from the room; the live one was not.
    assert manager.connection_count("match-1") == 1


async def test_broadcast_removes_the_socket_that_actually_failed_not_others() -> None:
    manager = ConnectionManager()
    dead_ws = FakeWebSocket(fail_send=True)
    live_ws = FakeWebSocket()
    await manager.connect("match-1", dead_ws, participant_id="token-dead")
    await manager.connect("match-1", live_ws, participant_id="token-live")

    await manager.broadcast("match-1", ServerPushEvent(event="chat_message", payload={"text": "hi"}))

    # A second broadcast proves the live socket is still registered and
    # working — it wasn't the one that got disconnected.
    await manager.broadcast("match-1", ServerPushEvent(event="chat_message", payload={"text": "again"}))
    assert live_ws.sent == [
        {"event": "chat_message", "payload": {"text": "hi"}},
        {"event": "chat_message", "payload": {"text": "again"}},
    ]


async def test_handle_client_message_persists_and_broadcasts_chat(repository: Repository) -> None:
    match_id = str(uuid.uuid4())
    await repository.create_match(match_id)
    ws = FakeWebSocket()
    await global_manager.connect(match_id, ws)
    try:
        reply = await handle_client_message(
            repository, match_id, "Ada", "Ada", {"action": "chat", "payload": {"message": "hello"}}
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
    reply = await handle_client_message(repository, match_id, "Ada", "Ada", {"action": "teleport"})
    assert reply is not None
    assert reply.event == "error"


async def test_handle_client_message_returns_error_for_invalid_schema(repository: Repository) -> None:
    reply = await handle_client_message(repository, "match-x", "Ada", "Ada", {"payload": {}})
    assert reply is not None
    assert reply.event == "error"


async def test_submit_move_valid_updates_state_and_broadcasts(repository: Repository) -> None:
    match_id = str(uuid.uuid4())
    await repository.create_match(match_id)
    ws = FakeWebSocket()
    await global_manager.connect(match_id, ws)
    try:
        reply = await handle_client_message(
            repository, match_id, "Ada", "Ada", {"action": "submit_move", "payload": {"move": 4}}
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
        await handle_client_message(
            repository, match_id, "Ada", "Ada", {"action": "submit_move", "payload": {"move": 0}}
        )
        reply = await handle_client_message(
            repository, match_id, "Ada", "Ada", {"action": "submit_move", "payload": {"move": 1}}
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
            repository, match_id, "Ada", "Ada", {"action": "submit_move", "payload": {"move": 99}}
        )
        assert reply is not None
        assert reply.event == "error"
    finally:
        clear_match(match_id)


async def test_third_player_gets_no_seat(repository: Repository) -> None:
    match_id = str(uuid.uuid4())
    await repository.create_match(match_id)
    try:
        await handle_client_message(
            repository, match_id, "Ada", "Ada", {"action": "submit_move", "payload": {"move": 0}}
        )
        await handle_client_message(
            repository, match_id, "Bob", "Bob", {"action": "submit_move", "payload": {"move": 1}}
        )
        reply = await handle_client_message(
            repository, match_id, "Cara", "Cara", {"action": "submit_move", "payload": {"move": 2}}
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
            await handle_client_message(
                repository, match_id, sender, sender, {"action": "submit_move", "payload": {"move": move}}
            )

        assert ws_x.sent[-1] == {"event": "game_over", "payload": {"result": "X"}}
        assert ws_o.sent[-1] == {"event": "game_over", "payload": {"result": "X"}}
        assert ws_x.closed is True
        assert ws_o.closed is True
        assert global_manager.connection_count(match_id) == 0
    finally:
        clear_match(match_id)


async def test_winning_moves_state_update_reports_no_current_turn(repository: Repository) -> None:
    """Regression: the state_update broadcast for the WINNING move itself
    reported the parity-computed current_turn (e.g. 'O' right after X's
    winning move) even though the game had already ended. A client that
    decides whether to act by checking current_turn == its own symbol (e.g.
    AgentSession.is_my_turn in client/agent.py) reads that state_update —
    which arrives before the follow-up game_over message is processed — and
    tries to submit another move/chat into a room the server is about to
    close, crashing with ConnectionClosedOK instead of just seeing the game
    end. The terminal move's state_update must report current_turn: None so
    no one is invited to act on it."""
    match_id = str(uuid.uuid4())
    await repository.create_match(match_id)
    ws_x, ws_o = FakeWebSocket(), FakeWebSocket()
    await global_manager.connect(match_id, ws_x)
    await global_manager.connect(match_id, ws_o)
    try:
        for sender, move in [("Ada", 0), ("Bob", 3), ("Ada", 1), ("Bob", 4), ("Ada", 2)]:
            await handle_client_message(
                repository, match_id, sender, sender, {"action": "submit_move", "payload": {"move": move}}
            )

        winning_state_update = ws_x.sent[-2]
        assert winning_state_update["event"] == "state_update"
        assert winning_state_update["payload"]["current_turn"] is None
    finally:
        clear_match(match_id)
