from typing import Any

from fastapi import WebSocket
from pydantic import BaseModel, ValidationError

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

    return ServerPushEvent(event="error", payload={"detail": f"Unknown action: {action.action}"})
