"""The ``GameInterface`` seam — the only way a game plugs into AgentArena (architecture.md §4.1).

A game module implements this ABC and is otherwise fully decoupled from transport. Seam rules:

- **The move payload is opaque to transport.** For TicTacToe it is an ``int`` cell ``0–8``; a
  future chess module might take algebraic notation. Only the game module interprets or validates
  it — the WebSocket layer, server, and UI pass it through unexamined.
- ``apply_move`` is the **sole legality authority**: it returns ``False`` for anything illegal
  (out-of-range, occupied, wrong type) and **never raises** on bad input.
- New games are **new modules**, never generalizations of an existing one.

This is a stable contract: any change to the method names/signatures below updates architecture.md
§4.1 **and** the contract test in ``tests/test_game_interface_contract.py`` in the same commit.
"""

from abc import ABC, abstractmethod
from typing import Any


class GameInterface(ABC):
    """Abstract base every game engine implements — pure logic, imports nothing from ``server/``."""

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """Return the structured board state, e.g. ``{"board": [...]}``."""

    @abstractmethod
    def get_valid_moves(self) -> list[Any]:
        """Return the legal moves available to the player whose turn it is."""

    @abstractmethod
    def apply_move(self, player: str, move: Any) -> bool:
        """Validate and apply ``move`` for ``player`` — the sole legality authority.

        Returns ``True`` when the move was legal and applied, ``False`` for any illegal move
        (out-of-range, occupied, wrong type). Never raises on bad input.
        """

    @abstractmethod
    def is_game_over(self) -> str | None:
        """Return the result once the game has ended, else ``None`` while ongoing.

        ``"X"``/``"O"`` for a winner, ``"draw"`` for a full board with no line, ``None`` if ongoing.
        """
