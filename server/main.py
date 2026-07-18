import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState

from server import auth
from server.database import async_session_maker, init_models
from server.repository import Repository
from server.schemas import JoinRequest, JoinResponse, MatchCreateResponse
from server.websockets import ServerPushEvent, handle_client_message, manager

TOKEN_MISSING_OR_INVALID = 4001


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    yield


app = FastAPI(title="Agent Arena", version="02.03.00", lifespan=lifespan)

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
    match_id = str(uuid.uuid4())
    async with async_session_maker() as session:
        await Repository(session).create_match(match_id)
    return MatchCreateResponse(match_id=match_id)


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
        async with async_session_maker() as session:
            repository = Repository(session)
            while True:
                try:
                    raw_data = await websocket.receive_json()
                except ValueError:
                    await manager.send_to(
                        websocket, ServerPushEvent(event="error", payload={"detail": "Malformed JSON"})
                    )
                    continue

                reply = await handle_client_message(repository, match_id, issued.player_name, raw_data)
                if reply is not None:
                    await manager.send_to(websocket, reply)

                # A game_over broadcast closes every connection in the room server-side
                # (including this one, mid-loop) via ConnectionManager.close_room — stop
                # before the next receive_json() hits an already-disconnected socket.
                if websocket.application_state != WebSocketState.CONNECTED:
                    break
    except WebSocketDisconnect:
        manager.disconnect(match_id, websocket)
