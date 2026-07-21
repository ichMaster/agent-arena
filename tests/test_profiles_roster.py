"""The persona roster loads, validates, and is genuinely contrasting (ARENA-OPUS-032). No paid call.

Persona *quality* is a demo judgement; here we only assert that both profiles are valid, distinct,
and drive the real create_llm_client (SDK patched — zero paid calls).
"""

from unittest.mock import MagicMock, patch

from agent.llm import AnthropicHaikuClient, create_llm_client
from agent.profile import AgentProfile

ROSTER = ["profiles/aggressive.yml", "profiles/cautious.yml"]


def test_all_profiles_load_and_validate() -> None:
    for path in ROSTER:
        profile = AgentProfile.load_from_yaml(path)
        assert profile.name
        assert profile.system_prompt.strip()
        assert profile.model_type == "haiku"
        assert 0.0 <= profile.temperature <= 1.0
        assert profile.memory_limit > 0


def test_personas_are_contrasting() -> None:
    aggressive = AgentProfile.load_from_yaml("profiles/aggressive.yml")
    cautious = AgentProfile.load_from_yaml("profiles/cautious.yml")
    assert aggressive.name != cautious.name                       # distinct identities
    assert cautious.temperature < aggressive.temperature          # calmer vs livelier
    assert aggressive.system_prompt != cautious.system_prompt


def test_each_profile_drives_the_real_factory() -> None:
    with patch("agent.llm.AsyncAnthropic", return_value=MagicMock()):  # no real SDK / network
        for path in ROSTER:
            profile = AgentProfile.load_from_yaml(path)
            client = create_llm_client(profile.model_type, "sk-test", profile.temperature)
            assert isinstance(client, AnthropicHaikuClient)
