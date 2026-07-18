import typing
from fastapi import WebSocket
from pydantic import BaseModel, Field
from games.tictactoe import TicTacToe

class ClientActionPayload(BaseModel):
    action: str
    payload: typing.Any = Field(default_factory=dict)

class ServerPushEvent(BaseModel):
    event_type: str
    data: typing.Any = Field(default_factory=dict)

class ActiveMatch:
    def __init__(self, match_id: str):
        self.match_id = match_id
        self.game = TicTacToe()
        self.player_symbols: dict[WebSocket, str] = {}

    def add_player(self, websocket: WebSocket):
        if len(self.player_symbols) == 0:
            self.player_symbols[websocket] = "X"
        elif len(self.player_symbols) == 1:
            self.player_symbols[websocket] = "O"

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.active_matches: dict[str, ActiveMatch] = {}

    async def connect(self, websocket: WebSocket, match_id: str):
        await websocket.accept()
        if match_id not in self.active_connections:
            self.active_connections[match_id] = []
            self.active_matches[match_id] = ActiveMatch(match_id)
            
        self.active_connections[match_id].append(websocket)
        self.active_matches[match_id].add_player(websocket)
        
        state = self.active_matches[match_id].game.get_state()
        symbol = self.active_matches[match_id].player_symbols[websocket]
        await websocket.send_json(ServerPushEvent(
            event_type="connected", 
            data={"symbol": symbol, "state": state}
        ).model_dump())

    def disconnect(self, websocket: WebSocket, match_id: str):
        if match_id in self.active_connections:
            try:
                self.active_connections[match_id].remove(websocket)
            except ValueError:
                pass
            if match_id in self.active_matches and websocket in self.active_matches[match_id].player_symbols:
                del self.active_matches[match_id].player_symbols[websocket]
            if not self.active_connections[match_id]:
                del self.active_connections[match_id]
                if match_id in self.active_matches:
                    del self.active_matches[match_id]

    async def broadcast(self, message: ServerPushEvent, match_id: str):
        if match_id in self.active_connections:
            data = message.model_dump()
            for connection in self.active_connections[match_id]:
                await connection.send_json(data)
