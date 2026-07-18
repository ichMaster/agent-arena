import abc
import os
from google import genai

class LLMClient(abc.ABC):
    @abc.abstractmethod
    async def generate_response(self, prompt: str) -> str:
        pass

class GeminiClient(LLMClient):
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-3.1-pro"

    async def generate_response(self, prompt: str) -> str:
        # Assuming google-genai supports async natively in future or wrapping sync:
        # For now, using standard sync generate_content via asyncio.to_thread if needed,
        # or just async native if it supports it. We'll use async native if available,
        # but standard python SDK usually uses `client.aio.models.generate_content`.
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return response.text
