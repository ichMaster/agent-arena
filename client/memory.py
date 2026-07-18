from collections import deque
from typing import Any


class MemoryWindow:
    """Rolling buffer of the last N chat messages and game events, used to
    give the LLM prompt short-term continuity across turns."""

    def __init__(self, maxlen: int = 10) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=maxlen)

    def record(self, kind: str, detail: str) -> None:
        self._events.append({"kind": kind, "detail": detail})

    def as_lines(self) -> list[str]:
        return [f"- [{event['kind']}] {event['detail']}" for event in self._events]

    def __len__(self) -> int:
        return len(self._events)
