import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.schemas import JoinRequest, JoinResponse, MatchCreateResponse

app = FastAPI(title="Agent Arena", version="01.01.00")

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
    return JoinResponse(token=str(uuid.uuid4()))
