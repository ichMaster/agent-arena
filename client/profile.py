from pathlib import Path

import yaml
from pydantic import BaseModel


class AgentProfile(BaseModel):
    name: str
    model_type: str
    temperature: float
    system_prompt: str
    memory_limit: int

    @classmethod
    def load_from_yaml(cls, path: str | Path) -> "AgentProfile":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)
