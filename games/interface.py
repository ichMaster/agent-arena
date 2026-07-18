from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

class GameInterface(ABC):
    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """
        Returns the current state of the game board.
        """
        pass

    @abstractmethod
    def get_valid_moves(self) -> List[Any]:
        """
        Returns a list of all valid moves currently available.
        """
        pass

    @abstractmethod
    def apply_move(self, player: str, move: Any) -> bool:
        """
        Applies a move on behalf of the player.
        Returns True if the move was successful, False otherwise.
        """
        pass

    @abstractmethod
    def is_game_over(self) -> Optional[str]:
        """
        Returns the winner ("X", "O", "Draw") if the game is over,
        or None if the game is still active.
        """
        pass
