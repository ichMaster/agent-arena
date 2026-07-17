from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
from server.websockets import manager, ClientActionPayload, ServerPushEvent
from pydantic import BaseModel, ValidationError
from server.database import async_session_maker
from server.repository import ArenaRepository

from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Agent Arena", version="05.01.00")

# Allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend web UI directly from the backend
app.mount("/ui", StaticFiles(directory="web", html=True), name="web")

@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}

class MatchResponse(BaseModel):
    match_id: str

@app.post("/api/v1/lobby/match", response_model=MatchResponse)
async def create_match():
    async with async_session_maker() as session:
        repo = ArenaRepository(session)
        match = await repo.create_match()
    return MatchResponse(match_id=str(match.id))

class JoinRequest(BaseModel):
    match_id: str
    player_name: str

class JoinResponse(BaseModel):
    token: str

@app.post("/api/v1/lobby/join", response_model=JoinResponse)
async def join_match(request: JoinRequest):
    return JoinResponse(token=str(uuid.uuid4()))

@app.websocket("/ws/match/{match_id}")
async def websocket_endpoint(websocket: WebSocket, match_id: str, token: str = None):
    if not token:
        await websocket.close(code=1008)
        return
    
    # Naive auth validation: check if token is a valid UUID
    try:
        uuid.UUID(token)
    except ValueError:
        await websocket.close(code=1008)
        return
        
    await manager.connect(websocket, match_id)
    try:
        while True:
            data = await websocket.receive_json()
            try:
                payload = ClientActionPayload(**data)
                if payload.action == "chat_message":
                    sender = payload.payload.get("sender", "Unknown")
                    message = payload.payload.get("message", "")
                    
                    # Persist to DB
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
    except RuntimeError as e:
        if "WebSocket is not connected" in str(e):
            manager.disconnect(websocket, match_id)
        else:
            raise
