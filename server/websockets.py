from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from fastapi import WebSocket
from games.tictactoe import TicTacToe

class ClientActionPayload(BaseModel):
    action: str
    payload: dict = Field(default_factory=dict)

class ServerPushEvent(BaseModel):
    event: str
    data: dict = Field(default_factory=dict)

class MatchContext:
    def __init__(self) -> None:
        self.game = TicTacToe()
        self.players: List[WebSocket] = []
        self.player_map: Dict[WebSocket, str] = {} # Map WebSocket to 'X', 'O', or 'Spectator'

    def add_player(self, websocket: WebSocket, symbol: str) -> None:
        self.players.append(websocket)
        self.player_map[websocket] = symbol
            
    def remove_player(self, websocket: WebSocket) -> None:
        if websocket in self.players:
            self.players.remove(websocket)
        if websocket in self.player_map:
            del self.player_map[websocket]

class ConnectionManager:
    def __init__(self) -> None:
        self.matches: Dict[str, MatchContext] = {}
        self.token_to_symbol: Dict[str, Dict[str, str]] = {} # match_id -> {token -> symbol}

    async def connect(self, websocket: WebSocket, match_id: str, token: str = "test-token") -> None:
        await websocket.accept()
        if match_id not in self.matches:
            self.matches[match_id] = MatchContext()
        
        symbol = self.token_to_symbol.get(match_id, {}).get(token, None)
        if not symbol:
            # Fallback for direct tests
            players_count = len(self.matches[match_id].players)
            if players_count == 0:
                symbol = 'X'
            elif players_count == 1:
                symbol = 'O'
            else:
                symbol = 'Spectator'
                
        self.matches[match_id].add_player(websocket, symbol)
        
        # Send initial state update to the connecting client
        state = self.matches[match_id].game.get_state()
        state["assigned_symbol"] = self.matches[match_id].player_map.get(websocket, "Spectator")
        push_event = ServerPushEvent(event="state_update", data=state)
        await websocket.send_json(push_event.model_dump())

    def disconnect(self, websocket: WebSocket, match_id: str) -> None:
        if match_id in self.matches:
            self.matches[match_id].remove_player(websocket)
            if not self.matches[match_id].players:
                del self.matches[match_id]

    async def broadcast(self, match_id: str, event: ServerPushEvent) -> None:
        if match_id in self.matches:
            for connection in list(self.matches[match_id].players):
                try:
                    await connection.send_json(event.model_dump())
                except Exception:
                    pass
                
    async def process_action(self, websocket: WebSocket, match_id: str, payload: ClientActionPayload) -> None:
        if match_id not in self.matches:
            return
            
        match_context = self.matches[match_id]
        
        if payload.action == "submit_move":
            player_symbol = match_context.player_map.get(websocket)
            
            if not player_symbol or player_symbol == 'Spectator':
                await websocket.send_json({"error": "You are not a player in this match."})
                return
                
            move = payload.payload.get("move")
            success = match_context.game.apply_move(player_symbol, move)
            
            if success:
                # Broadcast updated state
                state = match_context.game.get_state()
                push_event = ServerPushEvent(event="state_update", data=state)
                await self.broadcast(match_id, push_event)
                
                # Check for game over
                winner = match_context.game.is_game_over()
                if winner:
                    game_over_event = ServerPushEvent(event="game_over", data={"winner": winner})
                    await self.broadcast(match_id, game_over_event)
                    # Terminate all connections gracefully
                    for conn in list(match_context.players):
                        try:
                            await conn.close(code=1000)
                        except Exception:
                            pass
            else:
                # Send error to just this client
                await websocket.send_json({"error": "Invalid move."})

manager = ConnectionManager()
