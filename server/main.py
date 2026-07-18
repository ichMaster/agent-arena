from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
import uuid
from server.websockets import manager, ClientActionPayload, ServerPushEvent
from server.database import async_session_maker
from server.repository import ArenaRepository

from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

app = FastAPI(title="Agent Arena", version="05.01.00")

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
    new_match_id = str(uuid.uuid4())
    return MatchResponse(match_id=new_match_id)

@app.post("/api/v1/lobby/join", response_model=JoinResponse)
async def join_match(request: JoinRequest):
    # For now, generate a random temporary opaque Auth Token
    token = str(uuid.uuid4())
    return JoinResponse(token=token)

@app.websocket("/ws/match/{match_id}")
async def websocket_endpoint(websocket: WebSocket, match_id: str, token: str = None):
    if not token:
        await websocket.close(code=1008)
        return
        
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
