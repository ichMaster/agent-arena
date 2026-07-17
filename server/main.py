from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

app = FastAPI(title="Agent Arena", version="01.01.00")

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
