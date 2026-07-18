from typing import Dict, List
from fastapi import WebSocket
from pydantic import BaseModel

class ClientActionPayload(BaseModel):
    action: str
    payload: dict

class ServerPushEvent(BaseModel):
    event: str
    data: dict

class ConnectionManager:
    def __init__(self):
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
            # We iterate over a copy of the list because elements can be removed concurrently on disconnect
            for connection in list(self.active_connections[match_id]):
                try:
                    await connection.send_json(event.model_dump())
                except Exception:
                    # Connection might be dead, handled during lifecycle
                    pass

manager = ConnectionManager()
