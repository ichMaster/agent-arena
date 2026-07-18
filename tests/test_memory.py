from client.memory import MemoryWindow


def test_memory_window_records_and_lists_events() -> None:
    memory = MemoryWindow(maxlen=10)
    memory.record("chat", "Ada: gg")
    memory.record("move", "Player X played cell 4")
    assert len(memory) == 2
    lines = memory.as_lines()
    assert lines == ["- [chat] Ada: gg", "- [move] Player X played cell 4"]


def test_memory_window_respects_maxlen() -> None:
    memory = MemoryWindow(maxlen=3)
    for i in range(5):
        memory.record("move", f"move-{i}")
    assert len(memory) == 3
    # Oldest entries are dropped first — only the last 3 remain.
    assert memory.as_lines() == ["- [move] move-2", "- [move] move-3", "- [move] move-4"]
