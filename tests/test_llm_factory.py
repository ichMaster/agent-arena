"""Unit tests for create_llm_client dispatch + fail-fast API-key handling (architecture §4.2, §9).

No network, no paid call: the factory-haiku test patches the SDK, and the key helper reads from an
injected mapping. Confirms dispatch, unknown-type/empty-key rejection, and the missing-key abort.
"""

from unittest.mock import MagicMock, patch

import pytest

from agent.llm import AnthropicHaikuClient, LLMClient, create_llm_client, load_api_key


def test_create_llm_client_returns_haiku() -> None:
    with patch("agent.llm.AsyncAnthropic", return_value=MagicMock()) as ctor:
        client = create_llm_client("haiku", "sk-test", 0.5)
    assert isinstance(client, AnthropicHaikuClient)
    assert isinstance(client, LLMClient)  # the seam, not a concrete import
    ctor.assert_called_once()  # patched — no real SDK / no network


def test_create_llm_client_unknown_type_raises() -> None:
    with pytest.raises(ValueError):
        create_llm_client("gpt-4", "sk-test", 0.5)


def test_create_llm_client_empty_key_raises() -> None:
    with pytest.raises(ValueError):
        create_llm_client("haiku", "", 0.5)


def test_load_api_key_present() -> None:
    assert load_api_key({"ANTHROPIC_API_KEY": "sk-abc"}) == "sk-abc"


def test_load_api_key_missing_aborts() -> None:
    with pytest.raises(RuntimeError):
        load_api_key({})
    with pytest.raises(RuntimeError):
        load_api_key({"ANTHROPIC_API_KEY": "   "})  # empty after strip
