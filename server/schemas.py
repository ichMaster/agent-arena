"""Pydantic request/response models for the lobby REST surface (architecture.md §6.1).

The lobby is the only REST surface; game state is never polled over REST.
"""

from pydantic import BaseModel


class JoinRequest(BaseModel):
    """Body of ``POST /api/v1/lobby/join``."""

    match_id: str
    player_name: str
    spectator: bool = False


class MatchCreatedResponse(BaseModel):
    """Response of ``POST /api/v1/lobby/match``."""

    match_id: str


class JoinResponse(BaseModel):
    """Response of ``POST /api/v1/lobby/join`` — the opaque token is the participant_id (§6.3)."""

    token: str
