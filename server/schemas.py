"""Lobby request/response schemas (architecture.md §6.1). Pydantic models for the REST surface."""

from pydantic import BaseModel, ConfigDict


class JoinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: str
    player_name: str
    spectator: bool = False


class MatchCreatedResponse(BaseModel):
    match_id: str


class JoinResponse(BaseModel):
    token: str
