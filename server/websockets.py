from typing import Dict, List, Any
from pydantic import BaseModel, Field
from fastapi import WebSocket

class ClientActionPayload(BaseModel):
    action: str
    payload: dict = Field(default_factory=dict)

class ServerPushEvent(BaseModel):
    event: str
    data: dict = Field(default_factory=dict)

class ConnectionManager:
    def __init__(self):
        # Maps match_id to list of active WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, match_id: str):
        await websocket.accept()
        if match_id not in self.active_connections:
            self.active_connections[match_id] = []
        self.active_connections[match_id].append(websocket)

    def disconnect(self, websocket: WebSocket, match_id: str):
        if match_id in self.active_connections:
            if websocket in self.active_connections[match_id]:
                self.active_connections[match_id].remove(websocket)
            if not self.active_connections[match_id]:
                del self.active_connections[match_id]

    async def broadcast(self, match_id: str, event: ServerPushEvent):
        if match_id in self.active_connections:
            json_data = event.model_dump_json()
            for connection in self.active_connections[match_id]:
                await connection.send_text(json_data)

manager = ConnectionManager()
