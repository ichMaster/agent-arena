"""Contract test pinning the GameInterface seam (architecture.md §4.1).

If this test needs to change, the seam changed — update architecture.md §4.1 in the same commit.
No LLM, no paid call: pure signature/abstractness assertions.
"""

import inspect
from typing import Any

import pytest

from games.interface import GameInterface


def test_is_abstract_and_cannot_be_instantiated() -> None:
    assert inspect.isabstract(GameInterface)
    with pytest.raises(TypeError):
        GameInterface()  # type: ignore[abstract]


def test_a_partial_subclass_is_still_abstract() -> None:
    class Partial(GameInterface):
        def get_state(self) -> dict[str, Any]:
            return {}

        # deliberately missing the other three abstract methods

    assert inspect.isabstract(Partial)
    with pytest.raises(TypeError):
        Partial()  # type: ignore[abstract]


def test_exactly_the_four_abstract_methods() -> None:
    assert set(GameInterface.__abstractmethods__) == {
        "get_state",
        "get_valid_moves",
        "apply_move",
        "is_game_over",
    }


def test_method_signatures_are_pinned() -> None:
    sig = inspect.signature(GameInterface.get_state)
    assert list(sig.parameters) == ["self"]
    assert sig.return_annotation == dict[str, Any]

    sig = inspect.signature(GameInterface.get_valid_moves)
    assert list(sig.parameters) == ["self"]
    assert sig.return_annotation == list[Any]

    sig = inspect.signature(GameInterface.apply_move)
    assert list(sig.parameters) == ["self", "player", "move"]
    assert sig.parameters["player"].annotation is str
    assert sig.parameters["move"].annotation is Any
    assert sig.return_annotation is bool

    sig = inspect.signature(GameInterface.is_game_over)
    assert list(sig.parameters) == ["self"]
    assert sig.return_annotation == (str | None)
