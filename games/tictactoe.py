"""Tic-Tac-Toe — the first concrete ``GameInterface`` implementation (architecture.md §4.1).

Pure logic: imports nothing from ``server/``. The board is 9 cells, ``X`` moves first, a win is any
of the 8 lines, and a full board with no line is a ``"draw"``. ``apply_move`` is the sole legality
authority and never raises. Live state lives only in the cell list, so a game replays cleanly from
an empty board (the server reconstructs matches by replaying the move log).
"""

from typing import Any, Final

from games.interface import GameInterface

EMPTY: Final = ""
PLAYERS: Final[tuple[str, str]] = ("X", "O")
BOARD_SIZE: Final = 9

WINNING_LINES: Final[tuple[tuple[int, int, int], ...]] = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # columns
    (0, 4, 8), (2, 4, 6),             # diagonals
)


class TicTacToe(GameInterface):
    """A single Tic-Tac-Toe game — nine cells, ``X`` first, replayable from empty."""

    def __init__(self) -> None:
        self._board: list[str] = [EMPTY] * BOARD_SIZE

    def get_state(self) -> dict[str, Any]:
        # Return a copy so callers can never mutate authoritative state.
        return {"board": list(self._board)}

    def get_valid_moves(self) -> list[Any]:
        if self.is_game_over() is not None:
            return []
        return [cell for cell in range(BOARD_SIZE) if self._board[cell] == EMPTY]

    def apply_move(self, player: str, move: Any) -> bool:
        if self.is_game_over() is not None:
            return False
        if player not in PLAYERS:
            return False
        # bool is a subclass of int — exclude it so True/False are not read as cells 1/0.
        if not isinstance(move, int) or isinstance(move, bool):
            return False
        if move < 0 or move >= BOARD_SIZE:
            return False
        if self._board[move] != EMPTY:
            return False
        self._board[move] = player
        return True

    def is_game_over(self) -> str | None:
        for a, b, c in WINNING_LINES:
            if self._board[a] != EMPTY and self._board[a] == self._board[b] == self._board[c]:
                return self._board[a]
        if all(cell != EMPTY for cell in self._board):
            return "draw"
        return None
