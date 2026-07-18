from typing import Any

from fastapi import WebSocket
from pydantic import BaseModel


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
