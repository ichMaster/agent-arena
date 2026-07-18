import abc
import os
from google import genai
from google.genai import types
from pydantic import BaseModel

class AgentResponse(BaseModel):
    move: int
    comment: str

class LLMClient(abc.ABC):
    @abc.abstractmethod
    async def generate_response(self, prompt: str) -> str:
        pass
        
    @abc.abstractmethod
    async def generate_structured_response(self, prompt: str) -> AgentResponse:
        pass

class GeminiClient(LLMClient):
    def __init__(self, temperature: float = 0.7, model_name: str = "gemini-3.5-flash"):
        api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model = model_name
        self.temperature = temperature

    async def generate_response(self, prompt: str) -> str:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=self.temperature
            )
        )
        return response.text

    async def generate_structured_response(self, prompt: str) -> AgentResponse:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AgentResponse,
                temperature=self.temperature
            )
        )
        return AgentResponse.model_validate_json(response.text)
