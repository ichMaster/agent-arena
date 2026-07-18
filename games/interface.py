from abc import ABC, abstractmethod
from typing import Any


class GameInterface(ABC):
    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_valid_moves(self) -> list[Any]:
        raise NotImplementedError

    @abstractmethod
    def apply_move(self, player: str, move: Any) -> bool:
        raise NotImplementedError

    @abstractmethod
    def is_game_over(self) -> str | None:
        raise NotImplementedError
