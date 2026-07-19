from typing import Any

from fastapi import WebSocket
from pydantic import BaseModel, ValidationError

from server.match import clear_match, get_or_create_match, release_participant
from server.repository import Repository


class ClientActionPayload(BaseModel):
    action: str
    payload: dict[str, Any] = {}


class ServerPushEvent(BaseModel):
    event: str
    payload: dict[str, Any] = {}


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}
        # Tracks which participant owns each live socket, so disconnect() —
        # called both on a clean client disconnect and when broadcast() finds
        # a dead socket — can also free that participant's match seat.
        self._owners: dict[WebSocket, str] = {}

    def connection_count(self, match_id: str) -> int:
        return len(self._connections.get(match_id, []))

    async def connect(self, match_id: str, websocket: WebSocket, participant_id: str | None = None) -> None:
        await websocket.accept()
        self._connections.setdefault(match_id, []).append(websocket)
        if participant_id is not None:
            self._owners[websocket] = participant_id

    def disconnect(self, match_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(match_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections and match_id in self._connections:
            del self._connections[match_id]

        participant_id = self._owners.pop(websocket, None)
        if participant_id is not None:
            release_participant(match_id, participant_id)

    async def broadcast(self, match_id: str, event: ServerPushEvent) -> None:
        payload = event.model_dump()
        for websocket in list(self._connections.get(match_id, [])):
            try:
                await websocket.send_json(payload)
            except Exception:
                # A dead/stale socket must not abort delivery to the rest of
                # the room, and cleanup must target the socket that actually
                # failed — not whichever connection's own loop happens to be
                # running this broadcast.
                self.disconnect(match_id, websocket)

    async def send_to(self, websocket: WebSocket, event: ServerPushEvent) -> None:
        await websocket.send_json(event.model_dump())

    async def close_room(self, match_id: str, code: int = 1000) -> None:
        for websocket in list(self._connections.get(match_id, [])):
            await websocket.close(code=code)
            self._owners.pop(websocket, None)
        self._connections.pop(match_id, None)


manager = ConnectionManager()


async def send_joined_event(
    match_id: str, websocket: WebSocket, participant_id: str, is_spectator: bool = False
) -> None:
    """Sent once, right after a connection is accepted. A client cannot tell
    whose turn it is from a bare `current_turn` broadcast without first
    learning its own assigned symbol — this closes that gap before the
    client ever needs to act. A spectator connection never claims a seat:
    marking it before assign_symbol makes that refusal permanent, even if
    the spectator later (mistakenly or maliciously) sends a submit_move."""
    match = get_or_create_match(match_id)
    if is_spectator:
        match.mark_spectator(participant_id)
    symbol = match.assign_symbol(participant_id)
    state = match.game.get_state()
    await manager.send_to(
        websocket,
        ServerPushEvent(
            event="joined",
            payload={
                "symbol": symbol,
                "board": state["board"],
                "current_turn": match.current_turn,
                "valid_moves": match.game.get_valid_moves(),
            },
        ),
    )


async def handle_client_message(
    repository: Repository, match_id: str, participant_id: str, player_name: str, raw_data: dict[str, Any]
) -> ServerPushEvent | None:
    """Validate and route one inbound WS message. Returns an event to send back to the
    sender only (e.g. an error) or None if the message was already broadcast to the room."""
    try:
        action = ClientActionPayload.model_validate(raw_data)
    except ValidationError as exc:
        return ServerPushEvent(event="error", payload={"detail": str(exc)})

    if action.action == "chat":
        message = str(action.payload.get("message", ""))
        await repository.log_chat(match_id, sender=player_name, message=message)
        await manager.broadcast(
            match_id, ServerPushEvent(event="chat_message", payload={"sender": player_name, "message": message})
        )
        return None

    if action.action == "submit_move":
        return await _handle_submit_move(repository, match_id, participant_id, action.payload)

    return ServerPushEvent(event="error", payload={"detail": f"Unknown action: {action.action}"})


async def _handle_submit_move(
    repository: Repository, match_id: str, participant_id: str, payload: dict[str, Any]
) -> ServerPushEvent | None:
    match = get_or_create_match(match_id)
    symbol = match.assign_symbol(participant_id)
    if symbol is None:
        return ServerPushEvent(event="error", payload={"detail": "Match already has two players"})

    if match.current_turn != symbol:
        return ServerPushEvent(event="error", payload={"detail": "Not your turn"})

    move = payload.get("move")
    if not match.game.apply_move(symbol, move):
        return ServerPushEvent(event="error", payload={"detail": f"Invalid move: {move!r}"})

    await repository.log_move(match_id, player_id=symbol, move_payload={"move": move})

    state = match.game.get_state()
    result = match.game.is_game_over()
    await manager.broadcast(
        match_id,
        ServerPushEvent(
            event="state_update",
            payload={
                "board": state["board"],
                # None (not the parity-computed X/O) once this move ends the
                # game — Match.current_turn only tracks move parity and has
                # no idea the game just ended, so without this check the
                # winning move's own state_update would still claim it's the
                # other symbol's turn. A client that checks current_turn ==
                # its own symbol to decide whether to act (e.g.
                # AgentSession.is_my_turn in client/agent.py) would read that
                # and try to submit another move/chat — into a room the
                # very next broadcast (game_over) closes — crashing with
                # ConnectionClosedOK instead of just seeing the game end.
                "current_turn": None if result is not None else match.current_turn,
                "valid_moves": match.game.get_valid_moves(),
                "last_move": {"player": symbol, "move": move},
            },
        ),
    )

    if result is not None:
        await manager.broadcast(match_id, ServerPushEvent(event="game_over", payload={"result": result}))
        clear_match(match_id)
        await manager.close_room(match_id)

    return None
