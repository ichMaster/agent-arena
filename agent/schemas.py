"""Structured output schema for the agent's per-turn decision (architecture.md §7.3).

The agent replies with one structured ``{move, comment}`` per turn — its chosen move plus an
optional taunt. ``move`` is opaque to transport (validated against ``valid_moves`` client-side then
re-validated server-side); ``comment`` is the banter, broadcast as chat.
"""

from pydantic import BaseModel


class AgentResponse(BaseModel):
    move: int
    comment: str
