import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from server import auth
from server.schemas import JoinRequest, JoinResponse, MatchCreateResponse
from server.websockets import manager

TOKEN_MISSING_OR_INVALID = 4001

app = FastAPI(title="Agent Arena", version="01.02.00")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/lobby/match", response_model=MatchCreateResponse)
async def create_match() -> MatchCreateResponse:
    return MatchCreateResponse(match_id=str(uuid.uuid4()))


@app.post("/api/v1/lobby/join", response_model=JoinResponse)
async def join_match(request: JoinRequest) -> JoinResponse:
    token = auth.issue_token(match_id=request.match_id, player_name=request.player_name)
    return JoinResponse(token=token)


@app.websocket("/ws/match/{match_id}")
async def match_socket(websocket: WebSocket, match_id: str) -> None:
    token = websocket.query_params.get("token")
    issued = auth.validate_token(token, match_id) if token else None
    if issued is None:
        await websocket.close(code=TOKEN_MISSING_OR_INVALID)
        return

    await manager.connect(match_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(match_id, websocket)
