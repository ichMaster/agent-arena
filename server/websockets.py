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

    def add_player(self, websocket: WebSocket, requested_symbol: str = None):
        current_symbols = list(self.player_symbols.values())
        if requested_symbol and requested_symbol not in current_symbols:
            self.player_symbols[websocket] = requested_symbol
        elif "X" not in current_symbols:
            self.player_symbols[websocket] = "X"
        elif "O" not in current_symbols:
            self.player_symbols[websocket] = "O"

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.active_matches: dict[str, ActiveMatch] = {}

    async def connect(self, websocket: WebSocket, match_id: str, role: str = "player", symbol: str = None, first_move: str = None):
        await websocket.accept()
        if match_id not in self.active_connections:
            self.active_connections[match_id] = []
            self.active_matches[match_id] = ActiveMatch(match_id)
            
        self.active_connections[match_id].append(websocket)
        
        if first_move:
             self.active_matches[match_id].game.current_turn = first_move

        if role != "spectator":
            self.active_matches[match_id].add_player(websocket, symbol)
        
        state = self.active_matches[match_id].game.get_state()
        symbol = self.active_matches[match_id].player_symbols.get(websocket, "Spectator")
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
