from pydantic import BaseModel


class AgentResponse(BaseModel):
    move: int
    comment: str
