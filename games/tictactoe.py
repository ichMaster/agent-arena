import typing
from games.interface import GameInterface

class TicTacToe(GameInterface):
    def __init__(self) -> None:
        self.board: typing.List[typing.Optional[str]] = [None] * 9
        self.current_turn: str = "O"

    def get_state(self) -> typing.Dict[str, typing.Any]:
        return {
            "board": self.board,
            "current_turn": self.current_turn
        }

    def get_valid_moves(self) -> typing.List[typing.Any]:
        if self.is_game_over() is not None:
            return []
        return [i for i, cell in enumerate(self.board) if cell is None]

    def apply_move(self, player: str, move: typing.Any) -> bool:
        if not isinstance(move, int):
            return False
        if move < 0 or move > 8:
            return False
        if self.board[move] is not None:
            return False
        if player != self.current_turn:
            return False
        if self.is_game_over() is not None:
            return False
            
        self.board[move] = player
        self.current_turn = "O" if self.current_turn == "X" else "X"
        return True

    def is_game_over(self) -> typing.Optional[str]:
        winning_vectors = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],
            [0, 3, 6], [1, 4, 7], [2, 5, 8],
            [0, 4, 8], [2, 4, 6]
        ]
        
        for vector in winning_vectors:
            a, b, c = vector
            if self.board[a] is not None and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
                
        if all(cell is not None for cell in self.board):
            return "draw"
            
        return None
