from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class GameInterface(ABC):
    """
    Strict interface that all future game engines must implement.
    This establishes the polymorphic seam between the game rules
    and the WebSocket server orchestration.
    """

    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """Return the current game state as a JSON-serializable dictionary."""
        pass

    @abstractmethod
    def get_valid_moves(self) -> List[Any]:
        """Return a list of valid moves for the current state."""
        pass

    @abstractmethod
    def apply_move(self, player: str, move: Any) -> bool:
        """
        Apply a move for the given player.
        Returns True if the move was valid and successfully applied, False otherwise.
        """
        pass

    @abstractmethod
    def is_game_over(self) -> Optional[str]:
        """
        Check if the game is over.
        Returns the winning player's identifier, 'draw', or None if the game is still active.
        """
        pass
