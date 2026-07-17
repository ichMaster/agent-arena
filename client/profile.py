import yaml
from pydantic import BaseModel, Field

class AgentProfile(BaseModel):
    name: str
    model_type: str = Field(default="gemini-1.5-pro")
    temperature: float = Field(default=0.7)
    system_prompt: str
    memory_limit: int = Field(default=10)

    @classmethod
    def load_from_yaml(cls, filepath: str) -> "AgentProfile":
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        profile = AgentProfile.load_from_yaml(sys.argv[1])
        print(f"Loaded Profile: {profile.name}")
        print(f"Model: {profile.model_type} (Temp: {profile.temperature})")
        print(f"Memory Limit: {profile.memory_limit}")
        print(f"Prompt:\n{profile.system_prompt}")
    else:
        print("Usage: python profile.py <path_to_yaml>")
