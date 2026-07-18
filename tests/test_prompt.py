from client.memory import MemoryWindow
from client.prompt import SYSTEM_PERSONA, build_prompt


def test_build_prompt_includes_persona_board_and_valid_moves() -> None:
    memory = MemoryWindow()
    prompt = build_prompt(memory, board=[None] * 9, valid_moves=list(range(9)))
    assert SYSTEM_PERSONA in prompt
    assert "(none yet)" in prompt
    assert "Current board" in prompt
    assert "Valid moves: [0, 1, 2, 3, 4, 5, 6, 7, 8]" in prompt


def test_build_prompt_includes_memory_lines() -> None:
    memory = MemoryWindow()
    memory.record("chat", "Ada: good luck")
    memory.record("move", "Player X played cell 0")
    prompt = build_prompt(memory, board=["X"] + [None] * 8, valid_moves=list(range(1, 9)))
    assert "- [chat] Ada: good luck" in prompt
    assert "- [move] Player X played cell 0" in prompt
