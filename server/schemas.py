from pydantic import BaseModel, Field


class MatchCreateResponse(BaseModel):
    match_id: str = Field(..., description="UUID4 identifier for the newly created match")
