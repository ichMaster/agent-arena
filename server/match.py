from games.tictactoe import TicTacToe

_SYMBOLS = ("X", "O")


class Match:
    def __init__(self, match_id: str) -> None:
        self.match_id = match_id
        self.game = TicTacToe()
        self.player_symbols: dict[str, str] = {}

    def assign_symbol(self, player_name: str) -> str | None:
        """Returns this player's symbol, assigning the next free one on first
        contact. Returns None once two distinct players already hold X and O
        (i.e. this is a third/spectator connection with no seat to play)."""
        if player_name in self.player_symbols:
            return self.player_symbols[player_name]
        if len(self.player_symbols) >= 2:
            return None
        taken = set(self.player_symbols.values())
        symbol = next(s for s in _SYMBOLS if s not in taken)
        self.player_symbols[player_name] = symbol
        return symbol

    @property
    def current_turn(self) -> str:
        moves_played = 9 - len(self.game.get_valid_moves())
        return "X" if moves_played % 2 == 0 else "O"


_active_matches: dict[str, Match] = {}


def get_or_create_match(match_id: str) -> Match:
    if match_id not in _active_matches:
        _active_matches[match_id] = Match(match_id)
    return _active_matches[match_id]


def clear_match(match_id: str) -> None:
    _active_matches.pop(match_id, None)
