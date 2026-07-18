from games.tictactoe import TicTacToe

_SYMBOLS = ("X", "O")


class Match:
    def __init__(self, match_id: str) -> None:
        self.match_id = match_id
        self.game = TicTacToe()
        # Keyed by participant_id (a unique per-connection identity, e.g. the
        # auth token) rather than the player's chosen display name — two
        # different sessions can share a display name (the Web UI defaults
        # everyone to "Human"), and keying by name would silently merge them
        # into the same seat.
        self.player_symbols: dict[str, str] = {}

    def assign_symbol(self, participant_id: str) -> str | None:
        """Returns this participant's symbol, assigning the next free one on
        first contact. Returns None once two distinct participants already
        hold X and O (i.e. this is a third/spectator connection with no seat
        to play)."""
        if participant_id in self.player_symbols:
            return self.player_symbols[participant_id]
        if len(self.player_symbols) >= 2:
            return None
        taken = set(self.player_symbols.values())
        symbol = next(s for s in _SYMBOLS if s not in taken)
        self.player_symbols[participant_id] = symbol
        return symbol

    def release_seat(self, participant_id: str) -> None:
        """Frees this participant's seat (if any) so a new connection can
        take it — called when their connection drops. Without this, a
        mid-game disconnect would permanently strand the match, since
        assign_symbol refuses any third participant once two seats are held."""
        self.player_symbols.pop(participant_id, None)

    @property
    def current_turn(self) -> str:
        moves_played = 9 - len(self.game.get_valid_moves())
        return "X" if moves_played % 2 == 0 else "O"


_active_matches: dict[str, Match] = {}


def get_or_create_match(match_id: str) -> Match:
    if match_id not in _active_matches:
        _active_matches[match_id] = Match(match_id)
    return _active_matches[match_id]


def release_participant(match_id: str, participant_id: str) -> None:
    match = _active_matches.get(match_id)
    if match is not None:
        match.release_seat(participant_id)


def clear_match(match_id: str) -> None:
    _active_matches.pop(match_id, None)
