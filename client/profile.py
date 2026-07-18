from pydantic import BaseModel
import yaml
import os

class AgentProfile(BaseModel):
    name: str
    model_type: str
    temperature: float
    system_prompt: str
    memory_limit: int

def load_profile(filepath: str) -> AgentProfile:
    with open(filepath, 'r') as f:
        data = yaml.safe_load(f)
    return AgentProfile(**data)

if __name__ == "__main__":
    # Test script to load profile
    profile_path = os.path.join(os.path.dirname(__file__), "..", "profiles", "aggressive_bot.yml")
    profile = load_profile(profile_path)
    print(f"Loaded Profile: {profile.name} using {profile.model_type}")
