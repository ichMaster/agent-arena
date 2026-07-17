from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
from server.websockets import manager

app = FastAPI(title="Agent Arena", version="01.02.00")

# Allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}

class MatchResponse(BaseModel):
    match_id: str

@app.post("/api/v1/lobby/match", response_model=MatchResponse)
async def create_match():
    return MatchResponse(match_id=str(uuid.uuid4()))

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
            # ARENA-010 will implement routing, just keep connection alive for now
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, match_id)
