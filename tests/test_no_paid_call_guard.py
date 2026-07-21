"""The autouse no-paid-call guard makes the whole suite safe by construction (ARENA-OPUS-035, §11).

No local patch here — the guard in conftest.py must make an un-mocked create_llm_client harmless.
"""

from unittest.mock import MagicMock

import agent.llm as llm
from agent.llm import AnthropicHaikuClient, create_llm_client


def test_async_anthropic_is_patched_during_tests() -> None:
    # The autouse guard replaces the real SDK class with a dummy for every test.
    assert isinstance(llm.AsyncAnthropic, MagicMock)


def test_unmocked_factory_is_network_safe() -> None:
    # Building a client without any local patch must NOT create a real AsyncAnthropic.
    client = create_llm_client("haiku", "sk-fake-not-a-real-key", 0.5)
    assert isinstance(client, AnthropicHaikuClient)
    assert isinstance(client._client, MagicMock)  # backed by the dummy, no network client
