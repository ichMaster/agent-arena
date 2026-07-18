import pytest

from games.interface import GameInterface


def test_game_interface_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        GameInterface()
