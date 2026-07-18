import pytest
from pydantic import ValidationError

from client.profile import AgentProfile

PROFILES_DIR = "profiles"


def test_agent_profile_validates_direct_data() -> None:
    profile = AgentProfile(
        name="Test-Bot",
        model_type="gemini-3.1-pro",
        temperature=0.7,
        system_prompt="You are a test bot.",
        memory_limit=10,
    )
    assert profile.name == "Test-Bot"
    assert profile.temperature == 0.7


def test_agent_profile_rejects_missing_fields() -> None:
    with pytest.raises(ValidationError):
        AgentProfile(name="Incomplete-Bot")


def test_load_aggressive_bot_profile_from_yaml() -> None:
    profile = AgentProfile.load_from_yaml(f"{PROFILES_DIR}/aggressive_bot.yml")
    assert profile.name == "Aggressor-Prime"
    assert profile.model_type == "gemini-3.1-pro-preview"
    assert isinstance(profile.temperature, float)
    assert profile.memory_limit == 10


def test_load_cowardly_bot_profile_from_yaml() -> None:
    profile = AgentProfile.load_from_yaml(f"{PROFILES_DIR}/cowardly_bot.yml")
    assert profile.name == "Nervous-Nelly"
    assert profile.memory_limit == 6


def test_at_least_two_distinct_profiles_exist() -> None:
    aggressive = AgentProfile.load_from_yaml(f"{PROFILES_DIR}/aggressive_bot.yml")
    cowardly = AgentProfile.load_from_yaml(f"{PROFILES_DIR}/cowardly_bot.yml")
    assert aggressive.name != cowardly.name
    assert aggressive.system_prompt != cowardly.system_prompt
