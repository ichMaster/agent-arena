from typing import Dict, List, Any, Optional
from games.interface import GameInterface

class TicTacToe(GameInterface):
    def __init__(self) -> None:
        self.board: List[Optional[str]] = [None] * 9
        self.current_turn: str = 'X'

    def get_state(self) -> Dict[str, Any]:
        return {
            "board": self.board,
            "current_turn": self.current_turn,
            "status": self.is_game_over() or "ACTIVE"
        }

    def get_valid_moves(self) -> List[int]:
        return [i for i, cell in enumerate(self.board) if cell is None]

    def apply_move(self, player: str, move: Any) -> bool:
        if not isinstance(move, int) or move < 0 or move > 8:
            return False
        if self.board[move] is not None:
            return False
        if player != self.current_turn:
            return False
        # Set move and switch turn
        self.board[move] = player
        self.current_turn = 'O' if player == 'X' else 'X'
        return True

    def is_game_over(self) -> Optional[str]:
        winning_vectors = [
            # Rows
            (0, 1, 2), (3, 4, 5), (6, 7, 8),
            # Columns
            (0, 3, 6), (1, 4, 7), (2, 5, 8),
            # Diagonals
            (0, 4, 8), (2, 4, 6)
        ]
        
        for a, b, c in winning_vectors:
            if self.board[a] is not None and self.board[a] == self.board[b] == self.board[c]:
                # Return winner ("X" or "O")
                return self.board[a]
                
        if all(cell is not None for cell in self.board):
            return "draw"
            
        return None
