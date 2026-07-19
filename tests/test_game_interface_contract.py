"""Contract test pinning the ``GameInterface`` seam (architecture.md §4.1).

Any change to the four method names, their signatures, or the abstractness of the base class must
update architecture.md §4.1 and this test together (the contract-stability rule). No LLM, no paid
call — this is pure introspection of the seam.
"""

import inspect
from typing import Any

import pytest

from games.interface import GameInterface

EXPECTED_ABSTRACT_METHODS = frozenset(
    {"get_state", "get_valid_moves", "apply_move", "is_game_over"}
)

# name -> (ordered parameter names, {param: annotation}, return annotation)
EXPECTED_SIGNATURES: dict[str, tuple[list[str], dict[str, object], object]] = {
    "get_state": (["self"], {}, dict[str, Any]),
    "get_valid_moves": (["self"], {}, list[Any]),
    "apply_move": (["self", "player", "move"], {"player": str, "move": Any}, bool),
    "is_game_over": (["self"], {}, str | None),
}


def test_is_abstract_base_class() -> None:
    assert inspect.isabstract(GameInterface)


def test_abstract_method_names() -> None:
    assert GameInterface.__abstractmethods__ == EXPECTED_ABSTRACT_METHODS


@pytest.mark.parametrize("name", sorted(EXPECTED_ABSTRACT_METHODS))
def test_method_signature(name: str) -> None:
    expected_params, expected_annotations, expected_return = EXPECTED_SIGNATURES[name]
    signature = inspect.signature(getattr(GameInterface, name))
    assert list(signature.parameters) == expected_params
    for param_name, annotation in expected_annotations.items():
        assert signature.parameters[param_name].annotation == annotation
    assert signature.return_annotation == expected_return


def test_cannot_instantiate_bare_interface() -> None:
    with pytest.raises(TypeError):
        GameInterface()  # type: ignore[abstract]


def test_partial_subclass_cannot_be_instantiated() -> None:
    class PartialGame(GameInterface):
        def get_state(self) -> dict[str, Any]:
            return {"board": []}

        # Deliberately leaves get_valid_moves / apply_move / is_game_over unimplemented.

    assert inspect.isabstract(PartialGame)
    with pytest.raises(TypeError):
        PartialGame()  # type: ignore[abstract]
