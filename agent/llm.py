"""The LLMClient seam — the only way the agent talks to a model vendor (architecture.md §4.2).

Vendor-agnostic by design: `agent/agent.py` never imports a concrete client, only this abstraction
(and, from ARENA-OPUS-SONNET-018 onward, `create_llm_client`). Imports nothing from `server/` — the
agent is a pure external client, exactly like the Web UI.
"""

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(ABC):
    """One seam, one job: force the model to structured output and hand back a validated instance."""

    @abstractmethod
    async def generate_structured_response(self, prompt: str, schema: type[T]) -> T:
        """Return an instance of `schema`; the caller never parses raw text."""
