"""The ``LLMClient`` vendor seam — the only way the agent talks to a model (architecture.md §4.2).

Keeps agent logic free of any vendor SDK. Rules:

- Structured output is **forced at the client** and returned validated into the caller's ``schema``;
  the caller never parses raw text.
- The seam is **vendor-agnostic by design** — other vendors/tiers slot in as new ``LLMClient``
  implementations behind ``create_llm_client``; ``agent/agent.py`` never imports a concrete client.
- Imports nothing from ``server/`` — the agent is a pure external client.
- **Always mocked in tests** — no paid call in any test or CI run.

This is a stable contract: any change to the method name/signature updates architecture.md §4.2 and
the contract test (``tests/test_llm_contract.py``) in the same commit.
"""

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(ABC):
    """The model-vendor seam. Concrete clients force structured output and return it validated."""

    @abstractmethod
    async def generate_structured_response(self, prompt: str, schema: type[T]) -> T:
        """Return an instance of ``schema``, forcing the model to structured output."""
