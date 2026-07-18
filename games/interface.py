import abc
import typing

class GameInterface(abc.ABC):

    @abc.abstractmethod
    def get_state(self) -> typing.Dict[str, typing.Any]:
        pass

    @abc.abstractmethod
    def get_valid_moves(self) -> typing.List[typing.Any]:
        pass

    @abc.abstractmethod
    def apply_move(self, player: str, move: typing.Any) -> bool:
        pass

    @abc.abstractmethod
    def is_game_over(self) -> typing.Optional[str]:
        pass
