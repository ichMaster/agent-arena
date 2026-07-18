import typing
from fastapi import WebSocket
from pydantic import BaseModel, Field

class ClientActionPayload(BaseModel):
    action: str
    payload: typing.Any = Field(default_factory=dict)

class ServerPushEvent(BaseModel):
    event_type: str
    data: typing.Any = Field(default_factory=dict)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, match_id: str):
        await websocket.accept()
        if match_id not in self.active_connections:
            self.active_connections[match_id] = []
        self.active_connections[match_id].append(websocket)

    def disconnect(self, websocket: WebSocket, match_id: str):
        if match_id in self.active_connections:
            try:
                self.active_connections[match_id].remove(websocket)
            except ValueError:
                pass
            if not self.active_connections[match_id]:
                del self.active_connections[match_id]

    async def broadcast(self, message: ServerPushEvent, match_id: str):
        if match_id in self.active_connections:
            data = message.model_dump()
            for connection in self.active_connections[match_id]:
                await connection.send_json(data)
