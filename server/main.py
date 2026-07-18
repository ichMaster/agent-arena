from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

app = FastAPI(title="Agent Arena", version="01.01.00")

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
    return {"token": str(uuid.uuid4())}
