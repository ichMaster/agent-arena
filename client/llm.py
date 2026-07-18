from abc import ABC, abstractmethod
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

GEMINI_MODEL = "gemini-3.1-pro"

T = TypeVar("T", bound=BaseModel)


class LLMClient(ABC):
    @abstractmethod
    async def generate_response(self, prompt: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def generate_structured_response(self, prompt: str, schema: type[T]) -> T:
        raise NotImplementedError


class GeminiClient(LLMClient):
    def __init__(self, api_key: str, temperature: float = 0.9) -> None:
        self._client = genai.Client(api_key=api_key)
        self._temperature = temperature

    async def generate_response(self, prompt: str) -> str:
        response = await self._client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=self._temperature),
        )
        return response.text or ""

    async def generate_structured_response(self, prompt: str, schema: type[T]) -> T:
        response = await self._client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=self._temperature,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        return schema.model_validate_json(response.text or "")


def create_llm_client(model_type: str, api_key: str, temperature: float) -> LLMClient:
    """The only place that maps an AgentProfile's model_type to a concrete
    LLMClient — callers (client/agent.py) select a vendor purely via this
    config string, never by importing a vendor class directly."""
    if model_type.lower().startswith("gemini"):
        return GeminiClient(api_key=api_key, temperature=temperature)
    raise ValueError(f"Unsupported model_type {model_type!r}: only Gemini models are currently supported")
