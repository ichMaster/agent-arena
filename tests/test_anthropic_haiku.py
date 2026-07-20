"""Unit tests for AnthropicHaikuClient with the Anthropic SDK mocked (architecture §4.2, §7).

The SDK is patched in every test — no network, no real client, **no paid call**. Verifies the client
returns a validated AgentResponse, surfaces malformed / missing output as an error, and calls Haiku
with the right model id, temperature, and output_format.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pydantic
import pytest

from agent.llm import HAIKU_MODEL_ID, AnthropicHaikuClient
from agent.schemas import AgentResponse


def _a_validation_error() -> pydantic.ValidationError:
    try:
        AgentResponse(move="not-an-int", comment="x")  # type: ignore[arg-type]
    except pydantic.ValidationError as exc:
        return exc
    raise AssertionError("expected a ValidationError")


def _fake_client(parsed_output: object = None, parse_error: Exception | None = None) -> MagicMock:
    client = MagicMock()
    if parse_error is not None:
        client.messages.parse = AsyncMock(side_effect=parse_error)
    else:
        message = MagicMock()
        message.parsed_output = parsed_output
        client.messages.parse = AsyncMock(return_value=message)
    return client


async def test_returns_validated_agentresponse() -> None:
    fake = _fake_client(parsed_output=AgentResponse(move=4, comment="center is mine"))
    with patch("agent.llm.AsyncAnthropic", return_value=fake) as ctor:
        client = AnthropicHaikuClient(api_key="test-key", temperature=0.7)
        result = await client.generate_structured_response("your turn", AgentResponse)

    assert isinstance(result, AgentResponse)
    assert result.move == 4 and result.comment == "center is mine"
    ctor.assert_called_once()  # only the patched (fake) client — no real SDK / no network
    fake.messages.parse.assert_awaited_once()
    kwargs = fake.messages.parse.await_args.kwargs
    assert kwargs["model"] == HAIKU_MODEL_ID == "claude-haiku-4-5"
    assert kwargs["temperature"] == 0.7
    assert kwargs["output_format"] is AgentResponse


async def test_missing_structured_output_raises() -> None:
    fake = _fake_client(parsed_output=None)  # refusal / unparseable → not silently accepted
    with patch("agent.llm.AsyncAnthropic", return_value=fake):
        client = AnthropicHaikuClient(api_key="k", temperature=0.0)
        with pytest.raises(ValueError):
            await client.generate_structured_response("go", AgentResponse)


async def test_validation_error_propagates() -> None:
    fake = _fake_client(parse_error=_a_validation_error())  # malformed model output
    with patch("agent.llm.AsyncAnthropic", return_value=fake):
        client = AnthropicHaikuClient(api_key="k", temperature=0.0)
        with pytest.raises(pydantic.ValidationError):
            await client.generate_structured_response("go", AgentResponse)
