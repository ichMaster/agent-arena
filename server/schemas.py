from pydantic import BaseModel, Field


class MatchCreateResponse(BaseModel):
    match_id: str = Field(..., description="UUID4 identifier for the newly created match")


class JoinRequest(BaseModel):
    match_id: str
    player_name: str
    spectator: bool = Field(
        default=False, description="Join to watch only — never claims a player seat (X/O)"
    )


class JoinResponse(BaseModel):
    token: str = Field(..., description="Opaque auth token used to upgrade to a WebSocket connection")
