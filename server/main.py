import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState

from server import auth
from server.database import async_session_maker, init_models
from server.repository import Repository
from server.schemas import JoinRequest, JoinResponse, MatchCreateResponse
from server.websockets import ServerPushEvent, handle_client_message, manager, send_joined_event

TOKEN_MISSING_OR_INVALID = 4001


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    yield


app = FastAPI(title="Agent Arena", version="05.03.00", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/ui", StaticFiles(directory=WEB_DIR, html=True), name="ui")


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
    async with async_session_maker() as session:
        match = await Repository(session).get_match(request.match_id)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Match {request.match_id} not found")

    token = auth.issue_token(match_id=request.match_id, player_name=request.player_name)
    return JoinResponse(token=token)


@app.websocket("/ws/match/{match_id}")
async def match_socket(websocket: WebSocket, match_id: str) -> None:
    token = websocket.query_params.get("token")
    issued = auth.validate_token(token, match_id) if token else None
    if token is None or issued is None:
        await websocket.close(code=TOKEN_MISSING_OR_INVALID)
        return

    # The token is a unique per-join identity — used as the match "seat" key
    # (participant_id) so two sessions sharing a display name (e.g. the Web
    # UI's "Human" default) don't collide into the same seat. player_name is
    # still used wherever a human-readable label is needed (chat, logs).
    await manager.connect(match_id, websocket, participant_id=token)
    await send_joined_event(match_id, websocket, token)
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

                reply = await handle_client_message(repository, match_id, token, issued.player_name, raw_data)
                if reply is not None:
                    await manager.send_to(websocket, reply)

                # A game_over broadcast closes every connection in the room server-side
                # (including this one, mid-loop) via ConnectionManager.close_room — stop
                # before the next receive_json() hits an already-disconnected socket.
                if websocket.application_state != WebSocketState.CONNECTED:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        # A plain `except WebSocketDisconnect` here is not enough: with an
        # open DB session (the `async with async_session_maker()` above), a
        # client-initiated disconnect propagates as an anyio CancelledError
        # instead, which WebSocketDisconnect never catches — silently
        # skipping this cleanup and leaking the match seat forever. `finally`
        # runs regardless of which of those (or neither, on a clean `break`
        # from game_over) is what actually ended the loop, and CancelledError
        # still propagates onward afterward as it must.
        manager.disconnect(match_id, websocket)
