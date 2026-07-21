"""The AgentArena FastAPI app — lifespan, health, and the per-request Repository dependency.

Built with a `lifespan` context (no deprecated startup hooks, §3) that runs `init_models` on
startup. The REST surface lives under `/api/v1/*`; the lobby endpoints, the WebSocket hub, and the
`/ui` static mount arrive in later phases.

The app is built by `create_app` so tests can bind it to a throwaway engine/session maker and never
touch `./arena.db`; `app = create_app()` (bottom) is the process-wide ASGI app for
`uvicorn server.main:app`.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from server.auth import issue_token
from server.database import async_session_maker as default_session_maker
from server.database import engine as default_engine
from server.database import init_models
from server.repository import Repository
from server.schemas import JoinRequest, JoinResponse, MatchCreatedResponse

APP_VERSION = "01.03.00"  # bumped by the release process on each phase release


async def get_repository(request: Request) -> AsyncIterator[Repository]:
    """FastAPI dependency: a `Repository` over a per-request `AsyncSession` (§10)."""
    session_maker: async_sessionmaker[AsyncSession] = request.app.state.session_maker
    async with session_maker() as session:
        yield Repository(session)


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

    return application


app = create_app()
