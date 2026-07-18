from pydantic import BaseModel
import yaml
from pathlib import Path

class AgentProfile(BaseModel):
    name: str
    model_type: str
    temperature: float
    system_prompt: str
    memory_limit: int

    @classmethod
    def load_from_yaml(cls, path: Path | str) -> "AgentProfile":
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)
