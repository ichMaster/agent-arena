"""build_prompt — compose persona + memory + the pushed board into one decision prompt (§7.2).

The server pushes full turn state (v01.04), so the agent never round-trips to read state — it just
renders what it was handed. Deterministic, pure string composition; no model call here. The reply
contract matches AgentResponse{move, comment}.
"""

from agent.memory import MemoryWindow


def _render_board(board: list[str]) -> str:
    """3×3 grid; an empty cell shows its index so the model can name a cell by number."""
    cells = [board[i] if board[i] else str(i) for i in range(9)]
    rows = [" | ".join(cells[r : r + 3]) for r in range(0, 9, 3)]
    return "\n---------\n".join(rows)


def build_prompt(
    memory: MemoryWindow, board: list[str], valid_moves: list[int], persona: str
) -> str:
    """Render the persona, recent events, the board, and exactly the legal moves into one prompt."""
    events = memory.events()
    recent = "\n".join(f"- {e}" for e in events) if events else "- (nothing yet)"
    legal = ", ".join(str(m) for m in valid_moves)
    return (
        f"{persona}\n\n"
        "You are playing Tic-Tac-Toe. Recent events:\n"
        f"{recent}\n\n"
        "The board (a number = that empty cell's index; X/O = a taken cell):\n"
        f"{_render_board(board)}\n\n"
        f"Your legal moves are exactly: {legal}\n\n"
        "Reply with one `move` chosen from the legal moves above, and a short in-character `comment`."
    )
