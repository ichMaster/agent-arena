from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
import uuid
from server.websockets import manager, ClientActionPayload, ServerPushEvent
from server.database import async_session_maker
from server.repository import ArenaRepository

from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    from server.models import MatchModel, MoveLogModel, ChatLogModel
    from server.database import Base, engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="Agent Arena", version="05.03.00", lifespan=lifespan)

# Allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read(), status_code=200)

class MatchResponse(BaseModel):
    match_id: str

from typing import Optional

class JoinRequest(BaseModel):
    match_id: str
    player_name: str
    symbol: Optional[str] = None

class JoinResponse(BaseModel):
    token: str

@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/v1/lobby/match", response_model=MatchResponse)
async def create_match():
    new_match_id = str(uuid.uuid4())
    return MatchResponse(match_id=new_match_id)

@app.post("/api/v1/lobby/join", response_model=JoinResponse)
async def join_match(request: JoinRequest):
    async with async_session_maker() as session:
        from server.models import MatchModel, MatchStatus
        match = await session.get(MatchModel, request.match_id)
        if not match:
            match = MatchModel(id=request.match_id, status=MatchStatus.PENDING)
            session.add(match)
            await session.commit()
            
    token = str(uuid.uuid4())
    
    # Map token to requested or fallback symbol
    symbol = request.symbol
    if not symbol:
        if "spectator" in request.player_name.lower():
            symbol = "Spectator"
        else:
            match_tokens = [s for s in manager.token_to_symbol.get(request.match_id, {}).values() if s in ('X', 'O')]
            if len(match_tokens) == 0:
                symbol = 'X'
            elif len(match_tokens) == 1:
                symbol = 'O'
            else:
                symbol = 'Spectator'
                
    if request.match_id not in manager.token_to_symbol:
        manager.token_to_symbol[request.match_id] = {}
    manager.token_to_symbol[request.match_id][token] = symbol
    
    return JoinResponse(token=token)

from fastapi import WebSocketException

@app.websocket("/ws/match/{match_id}")
async def websocket_endpoint(websocket: WebSocket, match_id: str, token: str = None):
    if not token:
        raise WebSocketException(code=1008)
        
    try:
        uuid.UUID(token)
    except ValueError:
        raise WebSocketException(code=1008)
        
    await manager.connect(websocket, match_id, token)
    try:
        from starlette.websockets import WebSocketState
        while True:
            if websocket.client_state == WebSocketState.DISCONNECTED:
                break
            try:
                data = await websocket.receive_json()
            except RuntimeError:
                break
            try:
                payload = ClientActionPayload(**data)
                if payload.action == "chat_message":
                    sender = payload.payload.get("sender", "Unknown")
                    message = payload.payload.get("message", "")
                    
                    # Persist to Database
                    async with async_session_maker() as session:
                        repo = ArenaRepository(session)
                        await repo.log_chat(match_id, sender, message)
                    
                    # Broadcast
                    push_event = ServerPushEvent(
                        event="chat_message",
                        data={"sender": sender, "message": message}
                    )
                    await manager.broadcast(match_id, push_event)
                elif payload.action == "submit_move":
                    await manager.process_action(websocket, match_id, payload)
            except ValidationError:
                await websocket.send_json({"error": "Invalid payload format"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, match_id)
    finally:
        manager.disconnect(websocket, match_id)
