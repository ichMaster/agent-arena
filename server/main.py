from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
from server.websockets import ConnectionManager, ClientActionPayload, ServerPushEvent
from pydantic import BaseModel
import uuid

app = FastAPI(title="Agent Arena", version="01.03.00")

manager = ConnectionManager()
valid_tokens = set()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MatchResponse(BaseModel):
    match_id: str

class JoinRequest(BaseModel):
    match_id: str
    player_name: str

class JoinResponse(BaseModel):
    token: str

@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/v1/lobby/match", response_model=MatchResponse)
async def create_match():
    return {"match_id": str(uuid.uuid4())}

@app.post("/api/v1/lobby/join", response_model=JoinResponse)
async def join_match(request: JoinRequest):
    token = str(uuid.uuid4())
    valid_tokens.add(token)
    return {"token": token}

@app.websocket("/ws/match/{match_id}")
async def websocket_endpoint(websocket: WebSocket, match_id: str, token: str = None):
    if not token or token not in valid_tokens:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, match_id)
    try:
        while True:
            data = await websocket.receive_json()
            try:
                payload = ClientActionPayload(**data)
                if payload.action == "chat":
                    msg = ServerPushEvent(event_type="chat", data=payload.payload)
                    await manager.broadcast(msg, match_id)
            except Exception:
                await websocket.send_json({"error": "invalid payload"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, match_id)
