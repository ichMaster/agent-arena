"""The AgentArena FastAPI app — lifespan, health, the lobby REST, and the WebSocket hub.

Built with a `lifespan` context (no deprecated startup hooks, §3) that runs `init_models` on
startup. The REST surface lives under `/api/v1/*`; the `/ui` static mount arrives in v03.

The app is built by `create_app` so tests can bind it to a throwaway engine/session maker and never
touch `./arena.db`; `app = create_app()` (bottom) is the process-wide ASGI app for
`uvicorn server.main:app`.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from server.auth import issue_token, validate_token
from server.database import async_session_maker as default_session_maker
from server.database import engine as default_engine
from server.database import init_models
from server.match import assign_symbol, release_seat
from server.repository import Repository
from server.schemas import JoinRequest, JoinResponse, MatchCreatedResponse
from server.websockets import (
    ConnectionManager,
    chat_message_event,
    error_event,
    joined_event,
    parse_action,
)

APP_VERSION = "01.04.00"  # bumped by the release process on each phase release


async def get_repository(request: Request) -> AsyncIterator[Repository]:
    """FastAPI dependency: a `Repository` over a per-request `AsyncSession` (§10)."""
    session_maker: async_sessionmaker[AsyncSession] = request.app.state.session_maker
    async with session_maker() as session:
        yield Repository(session)


async def _current_state(
    session_maker: async_sessionmaker[AsyncSession], match_id: str
) -> tuple[list[Any], str | None, list[Any]]:
    """Derive (board, current_turn, valid_moves) by replaying the move log (§5.1)."""
    async with session_maker() as session:
        repo = Repository(session)
        game = await repo.reconstruct_game(match_id)
        turn = await repo.current_turn(match_id)
    return list(game.get_state()["board"]), turn, list(game.get_valid_moves())


async def _handle_action(
    websocket: WebSocket,
    manager: ConnectionManager,
    session_maker: async_sessionmaker[AsyncSession],
    match_id: str,
    token: str,
    symbol: str | None,
    action: str | None,
    payload: dict[str, Any],
) -> None:
    """Dispatch a client->server action (§5.4/§6.2)."""
    if action == "chat":
        # Sender label is whatever the join recorded for this connection (its assigned symbol, or
        # "observer" if seatless); chat is non-authoritative flavor and never affects game state.
        sender = symbol if symbol is not None else "observer"
        message = str(payload.get("message", ""))
        async with session_maker() as session:
            await Repository(session).log_chat(match_id, sender, message)
        await manager.broadcast(match_id, chat_message_event(sender, message))
        return

    await manager.send_to(websocket, error_event(f"unknown action: {action}"))


async def _ws_connection(
    websocket: WebSocket,
    match_id: str,
    manager: ConnectionManager,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Full WS lifecycle: token auth -> connect -> joined -> receive loop -> finally cleanup (§10)."""
    token = websocket.query_params.get("token")
    valid = False
    if token is not None:
        async with session_maker() as session:
            valid = await validate_token(Repository(session), match_id, token) is not None
    if token is None or not valid:
        await websocket.accept()
        await websocket.close(code=4001)  # bad/missing token
        return

    await manager.connect(match_id, websocket, token)
    try:
        symbol = await assign_symbol(session_maker, match_id, token)  # None for a spectator
        board, turn, valid_moves = await _current_state(session_maker, match_id)
        await manager.send_to(websocket, joined_event(symbol, board, turn, valid_moves))
        while True:
            raw = await websocket.receive_json()
            action, payload = parse_action(raw)
            await _handle_action(
                websocket, manager, session_maker, match_id, token, symbol, action, payload
            )
    except WebSocketDisconnect:
        pass
    finally:
        # Cleanup always runs (§10): remove the socket and release the seat for reconnects. A
        # client-initiated drop can surface as an async cancellation rather than
        # WebSocketDisconnect (§10) -- shield the release so that same cancellation can't also
        # interrupt its own await mid-commit and leak the seat.
        manager.disconnect(match_id, websocket)
        await asyncio.shield(release_seat(session_maker, match_id, token))


def create_app(
    *,
    db_engine: AsyncEngine | None = None,
    session_maker: async_sessionmaker[AsyncSession] | None = None,
) -> FastAPI:
    """Build the app bound to the given engine/session maker (defaults to the process-wide ones)."""
    resolved_engine = db_engine if db_engine is not None else default_engine
    resolved_maker = session_maker if session_maker is not None else default_session_maker

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await init_models(resolved_engine)
        yield

    application = FastAPI(title="AgentArena", version=APP_VERSION, lifespan=lifespan)
    application.state.session_maker = resolved_maker
    application.state.manager = ConnectionManager()  # in-memory live sockets (§10)

    @application.get("/api/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/api/v1/lobby/match", response_model=MatchCreatedResponse)
    async def create_match(
        repository: Repository = Depends(get_repository),
    ) -> MatchCreatedResponse:
        match_id = uuid.uuid4().hex
        await repository.create_match(match_id)
        return MatchCreatedResponse(match_id=match_id)

    @application.post("/api/v1/lobby/join", response_model=JoinResponse)
    async def join_match(
        body: JoinRequest,
        repository: Repository = Depends(get_repository),
    ) -> JoinResponse:
        if await repository.get_match(body.match_id) is None:
            raise HTTPException(status_code=404, detail="match not found")
        token = issue_token()
        await repository.add_participant(
            token, body.match_id, body.player_name, is_spectator=body.spectator
        )
        return JoinResponse(token=token)

    @application.websocket("/ws/match/{match_id}")
    async def ws_match(websocket: WebSocket, match_id: str) -> None:
        manager: ConnectionManager = websocket.app.state.manager
        maker: async_sessionmaker[AsyncSession] = websocket.app.state.session_maker
        await _ws_connection(websocket, match_id, manager, maker)

    return application


app = create_app()
