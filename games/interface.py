"""GameInterface — the game plug-in seam (architecture.md §4.1).

The **only** way a game enters the system. A game module implements this ABC and is otherwise fully
decoupled from transport. This is a **stable seam**: its four signatures are pinned by
``tests/test_game_interface_contract.py``; any change here updates architecture.md §4.1 **and** that
contract test in the same commit.

Seam rules:
- The move payload is **opaque to transport.** For TicTacToe it is an ``int`` cell ``0–8``; another
  game might take algebraic notation. Only the game module interprets/validates it — the WS layer,
  server, and UI pass it through unexamined.
- ``apply_move`` is the **sole legality authority**: it returns ``False`` for anything illegal
  (out-of-range, occupied, wrong type) and **never raises** on bad input.
- New games are **new modules**, never generalizations of an existing one.

Imports nothing from ``server/`` — pure logic.
"""

from abc import ABC, abstractmethod
from typing import Any


class GameInterface(ABC):
    """The abstract game seam: four typed methods, transport-agnostic."""

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """Return the structured board, e.g. ``{"board": [...]}``."""

    @abstractmethod
    def get_valid_moves(self) -> list[Any]:
        """Return the legal moves for the player to move."""

    @abstractmethod
    def apply_move(self, player: str, move: Any) -> bool:
        """Validate + apply ``move`` for ``player``; return ``False`` if illegal (never raise)."""

    @abstractmethod
    def is_game_over(self) -> str | None:
        """Return ``"X"`` | ``"O"`` | ``"draw"`` when over, or ``None`` while ongoing."""
