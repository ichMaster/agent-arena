import os
from abc import ABC, abstractmethod
from typing import Type, TypeVar, cast
from google import genai
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

class LLMClient(ABC):
    @abstractmethod
    async def generate_response(self, prompt: str) -> str:
        """
        Asynchronously generates a response from the LLM based on the prompt.
        """
        pass

    @abstractmethod
    async def generate_structured_response(self, prompt: str, response_schema: Type[T]) -> T:
        """
        Asynchronously generates a structured response validated against a Pydantic schema.
        """
        pass

class GeminiClient(LLMClient):
    def __init__(self, model_id: str = "gemini-3.1-pro") -> None:
        # genai.Client picks up GEMINI_API_KEY from environment variables automatically.
        # But we can also pass it explicitly if available.
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = genai.Client()
        self.model_id = model_id

    async def generate_response(self, prompt: str) -> str:
        response = await self.client.aio.models.generate_content(
            model=self.model_id,
            contents=prompt
        )
        return str(response.text)

    async def generate_structured_response(self, prompt: str, response_schema: Type[T]) -> T:
        response = await self.client.aio.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": response_schema,
            }
        )
        parsed = response.parsed
        if parsed is None:
            raise ValueError("Failed to parse structured response from Gemini API")
        return cast(T, parsed)

