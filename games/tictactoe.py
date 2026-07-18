from typing import Any

from games.interface import GameInterface

WINNING_LINES = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # columns
    (0, 4, 8), (2, 4, 6),             # diagonals
)


class TicTacToe(GameInterface):
    def __init__(self) -> None:
        self._board: list[str | None] = [None] * 9

    def get_state(self) -> dict[str, Any]:
        return {"board": list(self._board)}

    def get_valid_moves(self) -> list[int]:
        return [i for i, cell in enumerate(self._board) if cell is None]

    def apply_move(self, player: str, move: Any) -> bool:
        if not isinstance(move, int) or not (0 <= move <= 8):
            return False
        if self._board[move] is not None:
            return False
        self._board[move] = player
        return True

    def is_game_over(self) -> str | None:
        for a, b, c in WINNING_LINES:
            if self._board[a] is not None and self._board[a] == self._board[b] == self._board[c]:
                return self._board[a]
        if all(cell is not None for cell in self._board):
            return "draw"
        return None
