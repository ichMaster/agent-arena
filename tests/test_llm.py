from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from client.llm import GEMINI_MODEL, GeminiClient, LLMClient, create_llm_client


def test_llm_client_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        LLMClient()


def test_gemini_model_is_a_real_callable_model_id() -> None:
    """Regression: GEMINI_MODEL was hardcoded to "gemini-3.1-pro", which does
    not exist as an API model id — real calls 404'd with "models/gemini-3.1-pro
    is not found ... or is not supported for generateContent". The real id
    (confirmed via a live ListModels call, a free metadata request — no
    generateContent call was made) is "gemini-3.1-pro-preview". Pinned here so
    a future edit can't silently drift back to the non-existent bare name."""
    assert GEMINI_MODEL == "gemini-3.1-pro-preview"


async def test_gemini_client_returns_text_from_sdk_response() -> None:
    fake_response = MagicMock(text="I claim the center square.")
    with patch("client.llm.genai.Client") as fake_client_cls:
        fake_client_cls.return_value.aio.models.generate_content = AsyncMock(return_value=fake_response)

        client = GeminiClient(api_key="test-key")
        result = await client.generate_response("What is your move?")

    assert result == "I claim the center square."


async def test_gemini_client_uses_expected_model_and_prompt() -> None:
    fake_response = MagicMock(text="ok")
    with patch("client.llm.genai.Client") as fake_client_cls:
        generate_mock = AsyncMock(return_value=fake_response)
        fake_client_cls.return_value.aio.models.generate_content = generate_mock

        client = GeminiClient(api_key="test-key", temperature=0.4)
        await client.generate_response("prompt text")

    _, kwargs = generate_mock.call_args
    assert kwargs["model"] == GEMINI_MODEL
    assert kwargs["contents"] == "prompt text"
    assert kwargs["config"].temperature == 0.4


async def test_gemini_client_never_calls_real_api() -> None:
    """Guards against accidentally hitting the network/paid API in CI: the SDK
    Client constructor itself must be mocked, not just the network layer."""
    with patch("client.llm.genai.Client") as fake_client_cls:
        GeminiClient(api_key="test-key")
    fake_client_cls.assert_called_once_with(api_key="test-key")


def test_create_llm_client_selects_gemini_for_gemini_model_types() -> None:
    with patch("client.llm.genai.Client"):
        client = create_llm_client("gemini-3.1-pro", api_key="test-key", temperature=0.5)
    assert isinstance(client, GeminiClient)


def test_create_llm_client_is_case_insensitive() -> None:
    with patch("client.llm.genai.Client"):
        client = create_llm_client("Gemini-1.5-Flash", api_key="test-key", temperature=0.5)
    assert isinstance(client, GeminiClient)


def test_create_llm_client_rejects_unsupported_vendors() -> None:
    """AgentProfile.model_type must actually drive vendor selection — this
    would previously never be checked at all, since agent code hardcoded
    GeminiClient regardless of what a profile's model_type said."""
    with pytest.raises(ValueError, match="claude-3-opus"):
        create_llm_client("claude-3-opus", api_key="test-key", temperature=0.5)
