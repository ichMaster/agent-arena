"""Agent structured output (architecture.md §7.3).

The one shape the model must return each turn. `move` is opaque to transport (validated against
valid_moves client-side, then re-validated server-side); `comment` is the taunt/banter broadcast as
chat.
"""

from pydantic import BaseModel


class AgentResponse(BaseModel):
    move: int
    comment: str
