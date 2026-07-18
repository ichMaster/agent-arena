import pytest
from games.interface import GameInterface

def test_game_interface_abstract():
    # Attempting to instantiate GameInterface directly must raise TypeError
    with pytest.raises(TypeError):
        GameInterface()
