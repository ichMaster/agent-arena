import os
from abc import ABC, abstractmethod
from pydantic import BaseModel
from google import genai
from google.genai import types

class AgentResponse(BaseModel):
    move: int
    comment: str

class LLMClient(ABC):
    @abstractmethod
    async def generate_response(self, prompt: str) -> AgentResponse:
        """Asynchronously generates a structured response from the LLM based on the prompt."""
        pass

class GeminiClient(LLMClient):
    def __init__(self, model_id: str = "gemini-3.1-pro-preview", temperature: float = 0.7):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing")
        self.client = genai.Client(api_key=api_key)
        self.model_id = model_id
        self.temperature = temperature
        
    async def generate_response(self, prompt: str) -> AgentResponse:
        # Since google-genai is mostly synchronous by default, we should ideally run it in a threadpool
        # if we strictly need non-blocking async, but they also have async support in some clients.
        # For simplicity with the standard SDK, we use asyncio.to_thread to make it non-blocking.
        import asyncio
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=self.temperature,
                response_mime_type="application/json",
                response_schema=AgentResponse,
            )
        )
        return AgentResponse.model_validate_json(response.text)

async def _test():
    import dotenv
    dotenv.load_dotenv()
    
    print("[*] Testing GeminiClient...")
    try:
        client = GeminiClient()
        print(f"[*] Sending prompt to {client.model_id}...")
        resp = await client.generate_response("Say 'Hello, Agent Arena!'")
        print(f"[+] Response: {resp}")
    except Exception as e:
        print(f"[-] Test failed: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(_test())
