import pytest
from games.interface import GameInterface

def test_game_interface_instantiation():
    """
    Ensure GameInterface is truly abstract and cannot be instantiated directly.
    """
    with pytest.raises(TypeError) as exc:
        GameInterface()
    
    assert "Can't instantiate abstract class" in str(exc.value)
