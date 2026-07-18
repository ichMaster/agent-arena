import pytest
from pathlib import Path
from client.profile import AgentProfile

def test_load_aggressive_profile():
    profile_path = Path("profiles/aggressive_bot.yml")
    assert profile_path.exists()
    
    profile = AgentProfile.load_from_yaml(profile_path)
    assert profile.name == "AggressiveBot"
    assert profile.model_type == "gemini-2.5-flash"
    assert profile.temperature == 0.7
    assert "aggressive" in profile.system_prompt.lower()
    assert profile.memory_limit == 10

def test_load_defensive_profile():
    profile_path = Path("profiles/defensive_bot.yml")
    assert profile_path.exists()
    
    profile = AgentProfile.load_from_yaml(profile_path)
    assert profile.name == "DefensiveBot"
    assert profile.model_type == "gemini-2.5-flash"
    assert profile.temperature == 0.2
    assert "defensive" in profile.system_prompt.lower()
    assert profile.memory_limit == 10
