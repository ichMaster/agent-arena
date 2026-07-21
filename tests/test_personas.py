"""Two contrasting personas (ARENA-OPUS-OPUS-032, roadmap §v04.01). No LLM, no paid call."""

from unittest.mock import MagicMock, patch

from agent.llm import AnthropicHaikuClient, create_llm_client
from agent.profile import AgentProfile


def test_both_personas_load_and_validate() -> None:
    for path in ("profiles/aggressive.yml", "profiles/cautious.yml"):
        profile = AgentProfile.load_from_yaml(path)
        assert 0.0 <= profile.temperature <= 1.0
        assert profile.memory_limit > 0
        assert profile.model_type == "haiku"


def test_personas_are_visibly_distinct() -> None:
    aggressive = AgentProfile.load_from_yaml("profiles/aggressive.yml")
    cautious = AgentProfile.load_from_yaml("profiles/cautious.yml")
    assert aggressive.name == "Ironclaw"
    assert cautious.name == "Bastion"
    assert aggressive.name != cautious.name
    assert cautious.temperature < aggressive.temperature  # wary defender is calmer
    assert aggressive.system_prompt != cautious.system_prompt


def test_cautious_profile_drives_the_real_llm_factory() -> None:
    profile = AgentProfile.load_from_yaml("profiles/cautious.yml")
    with patch("agent.llm.AsyncAnthropic", return_value=MagicMock()):
        client = create_llm_client(profile.model_type, "sk-test", profile.temperature)
    assert isinstance(client, AnthropicHaikuClient)
