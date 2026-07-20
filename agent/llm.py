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

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# The Anthropic Haiku model id — a single config constant, confirmed against the live model list.
HAIKU_MODEL_ID = "claude-haiku-4-5"
_MAX_TOKENS = 1024


class LLMClient(ABC):
    """The model-vendor seam. Concrete clients force structured output and return it validated."""

    @abstractmethod
    async def generate_structured_response(self, prompt: str, schema: type[T]) -> T:
        """Return an instance of ``schema``, forcing the model to structured output."""


class AnthropicHaikuClient(LLMClient):
    """The only ``LLMClient`` implementation — Anthropic Haiku via the async SDK (§4.2, §7).

    Structured output is forced with ``messages.parse(output_format=schema)`` and the validated
    instance is returned, so the caller never parses raw text. The API key lives only in this process.
    Always mocked in tests — no paid call.
    """

    def __init__(self, api_key: str, temperature: float) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._temperature = temperature

    async def generate_structured_response(self, prompt: str, schema: type[T]) -> T:
        messages: list[MessageParam] = [{"role": "user", "content": prompt}]
        message = await self._client.messages.parse(
            model=HAIKU_MODEL_ID,
            max_tokens=_MAX_TOKENS,
            temperature=self._temperature,
            messages=messages,
            output_format=schema,
        )
        parsed = message.parsed_output
        if parsed is None:  # refusal / no structured output — never silently accepted
            raise ValueError("Anthropic Haiku returned no structured output")
        return parsed
