from typing import List

class MemoryWindow:
    def __init__(self, limit: int = 10) -> None:
        self.limit = limit
        self.history: List[str] = []

    def add(self, event_str: str) -> None:
        self.history.append(event_str)
        if len(self.history) > self.limit:
            self.history.pop(0)

    def get_context(self) -> str:
        return "\n".join(self.history)
