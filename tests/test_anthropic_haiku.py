"""AnthropicHaikuClient tests (ARENA-OPUS-OPUS-017). The SDK is ALWAYS patched -- no network, no paid
call. Confirms structured output is returned validated and malformed output surfaces as an error.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.llm import HAIKU_MODEL_ID, AnthropicHaikuClient
from agent.schemas import AgentResponse


def _mock_anthropic_returning(parsed: Any) -> MagicMock:
    """Build a fake AsyncAnthropic whose messages.parse returns a message with `.parsed_output`."""
    client = MagicMock()
    client.messages.parse = AsyncMock(return_value=SimpleNamespace(parsed_output=parsed))
    return client


async def test_returns_validated_agent_response() -> None:
    fake = _mock_anthropic_returning(AgentResponse(move=4, comment="center"))
    with patch("agent.llm.AsyncAnthropic", return_value=fake) as ctor:
        client = AnthropicHaikuClient(api_key="sk-test", temperature=0.5)
        result = await client.generate_structured_response("prompt", AgentResponse)
    assert result == AgentResponse(move=4, comment="center")
    ctor.assert_called_once_with(api_key="sk-test")  # the real SDK class never ran
    # The request used the single Haiku model-id constant and the passed temperature.
    _, kwargs = fake.messages.parse.call_args
    assert kwargs["model"] == HAIKU_MODEL_ID
    assert kwargs["temperature"] == 0.5
    assert kwargs["output_format"] is AgentResponse


async def test_unparsed_output_raises() -> None:
    fake = _mock_anthropic_returning(None)  # model reply that didn't parse
    with patch("agent.llm.AsyncAnthropic", return_value=fake):
        client = AnthropicHaikuClient(api_key="sk-test")
        with pytest.raises(ValueError):
            await client.generate_structured_response("prompt", AgentResponse)


def test_model_id_is_the_confirmed_haiku_constant() -> None:
    assert HAIKU_MODEL_ID == "claude-haiku-4-5"
