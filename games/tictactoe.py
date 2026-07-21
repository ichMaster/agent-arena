"""TicTacToe — the first concrete GameInterface (architecture.md §4.1).

Pure logic: a 9-cell board, ``X`` first, the 8 winning lines, ``"draw"`` when the board fills with no
line. The move payload is an ``int`` cell ``0–8``. ``apply_move`` is the sole legality authority and
never raises on bad input. Imports nothing from ``server/``.
"""

from typing import Any

from games.interface import GameInterface

_SYMBOLS = ("X", "O")
_WINNING_LINES: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # columns
    (0, 4, 8), (2, 4, 6),             # diagonals
)


class TicTacToe(GameInterface):
    """3×3 Tic-Tac-Toe. ``X`` moves first; the board is a flat 9-element list of ``""``/``"X"``/``"O"``."""

    def __init__(self) -> None:
        self._board: list[str] = [""] * 9

    def get_state(self) -> dict[str, Any]:
        return {"board": list(self._board)}

    def get_valid_moves(self) -> list[Any]:
        # No legal moves once the game is over — a won board is terminal even if cells remain.
        if self.is_game_over() is not None:
            return []
        return [i for i, cell in enumerate(self._board) if cell == ""]

    def apply_move(self, player: str, move: Any) -> bool:
        # Sole legality authority: reject anything illegal, never raise.
        if self.is_game_over() is not None:
            return False
        if player not in _SYMBOLS:
            return False
        # bool is a subclass of int — reject it explicitly so True/False can't pose as a cell index.
        if isinstance(move, bool) or not isinstance(move, int):
            return False
        if move < 0 or move > 8:
            return False
        if self._board[move] != "":
            return False
        self._board[move] = player
        return True

    def is_game_over(self) -> str | None:
        for a, b, c in _WINNING_LINES:
            if self._board[a] != "" and self._board[a] == self._board[b] == self._board[c]:
                return self._board[a]
        if all(cell != "" for cell in self._board):
            return "draw"
        return None
