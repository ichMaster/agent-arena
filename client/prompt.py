from typing import Any

from client.memory import MemoryWindow

SYSTEM_PERSONA = "You are an arrogant Tic-Tac-Toe master. Never lose."


def build_prompt(memory: MemoryWindow, board: list[Any], valid_moves: list[int]) -> str:
    lines = [SYSTEM_PERSONA, "", "Recent activity:"]
    lines.extend(memory.as_lines() or ["(none yet)"])
    lines.append("")
    lines.append(f"Current board (index -> mark, null = empty): {board}")
    lines.append(f"Valid moves: {valid_moves}")
    lines.append("")
    lines.append(
        "Respond with a single JSON object matching this shape: "
        '{"move": <int, one of the valid moves above>, "comment": <a short, arrogant taunt>}.'
    )
    return "\n".join(lines)
