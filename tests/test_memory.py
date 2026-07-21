"""MemoryWindow tests (ARENA-OPUS-OPUS-020). Pure logic, no LLM, no paid call."""

import pytest

from agent.memory import MemoryWindow


def test_records_moves_and_chat_in_order() -> None:
    mem = MemoryWindow(limit=5)
    mem.record_move("X", 4)
    mem.record_chat("O", "nice try")
    mem.record_move("O", 0)
    assert mem.events() == ["X played 4", 'O said: "nice try"', "O played 0"]
    assert len(mem) == 3


def test_evicts_oldest_beyond_limit() -> None:
    mem = MemoryWindow(limit=2)
    mem.record_move("X", 0)
    mem.record_move("O", 1)
    mem.record_move("X", 2)  # evicts "X played 0"
    assert mem.events() == ["O played 1", "X played 2"]
    assert len(mem) == 2


def test_events_returns_a_copy() -> None:
    mem = MemoryWindow(limit=3)
    mem.record_move("X", 4)
    snapshot = mem.events()
    snapshot.append("tampered")
    assert mem.events() == ["X played 4"]  # internal state unaffected


def test_non_positive_limit_raises() -> None:
    for bad in (0, -1):
        with pytest.raises(ValueError):
            MemoryWindow(limit=bad)
