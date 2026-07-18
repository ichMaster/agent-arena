import pytest
from games.interface import GameInterface

def test_instantiate_abstract_class():
    with pytest.raises(TypeError):
        GameInterface() # type: ignore
