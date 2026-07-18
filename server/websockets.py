from typing import Any

from fastapi import WebSocket
from pydantic import BaseModel, ValidationError

from server.match import clear_match, get_or_create_match
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

    def connection_count(self, match_id: str) -> int:
        return len(self._connections.get(match_id, []))

    async def connect(self, match_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(match_id, []).append(websocket)

    def disconnect(self, match_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(match_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections and match_id in self._connections:
            del self._connections[match_id]

    async def broadcast(self, match_id: str, event: ServerPushEvent) -> None:
        for websocket in list(self._connections.get(match_id, [])):
            await websocket.send_json(event.model_dump())

    async def send_to(self, websocket: WebSocket, event: ServerPushEvent) -> None:
        await websocket.send_json(event.model_dump())

    async def close_room(self, match_id: str, code: int = 1000) -> None:
        for websocket in list(self._connections.get(match_id, [])):
            await websocket.close(code=code)
        self._connections.pop(match_id, None)


manager = ConnectionManager()


async def handle_client_message(
    repository: Repository, match_id: str, sender: str, raw_data: dict[str, Any]
) -> ServerPushEvent | None:
    """Validate and route one inbound WS message. Returns an event to send back to the
    sender only (e.g. an error) or None if the message was already broadcast to the room."""
    try:
        action = ClientActionPayload.model_validate(raw_data)
    except ValidationError as exc:
        return ServerPushEvent(event="error", payload={"detail": str(exc)})

    if action.action == "chat":
        message = str(action.payload.get("message", ""))
        await repository.log_chat(match_id, sender=sender, message=message)
        await manager.broadcast(
            match_id, ServerPushEvent(event="chat_message", payload={"sender": sender, "message": message})
        )
        return None

    if action.action == "submit_move":
        return await _handle_submit_move(repository, match_id, sender, action.payload)

    return ServerPushEvent(event="error", payload={"detail": f"Unknown action: {action.action}"})


async def _handle_submit_move(
    repository: Repository, match_id: str, sender: str, payload: dict[str, Any]
) -> ServerPushEvent | None:
    match = get_or_create_match(match_id)
    symbol = match.assign_symbol(sender)
    if symbol is None:
        return ServerPushEvent(event="error", payload={"detail": "Match already has two players"})

    if match.current_turn != symbol:
        return ServerPushEvent(event="error", payload={"detail": "Not your turn"})

    move = payload.get("move")
    if not match.game.apply_move(symbol, move):
        return ServerPushEvent(event="error", payload={"detail": f"Invalid move: {move!r}"})

    await repository.log_move(match_id, player_id=symbol, move_payload={"move": move})

    state = match.game.get_state()
    await manager.broadcast(
        match_id,
        ServerPushEvent(
            event="state_update",
            payload={
                "board": state["board"],
                "current_turn": match.current_turn,
                "valid_moves": match.game.get_valid_moves(),
                "last_move": {"player": symbol, "move": move},
            },
        ),
    )

    result = match.game.is_game_over()
    if result is not None:
        await manager.broadcast(match_id, ServerPushEvent(event="game_over", payload={"result": result}))
        clear_match(match_id)
        await manager.close_room(match_id)

    return None
