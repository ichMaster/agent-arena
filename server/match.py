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
        # Participants who explicitly joined to watch, not play. Tracked
        # separately so assign_symbol can permanently refuse them a seat —
        # without this, a spectator who joins before the match fills up
        # would accidentally BE one of the two players, and a genuine third
        # player would find no seat left.
        self.spectator_ids: set[str] = set()

    def mark_spectator(self, participant_id: str) -> None:
        if participant_id in self.player_symbols:
            return  # already holds a real seat — can't retroactively become a spectator
        self.spectator_ids.add(participant_id)

    def assign_symbol(self, participant_id: str) -> str | None:
        """Returns this participant's symbol, assigning the next free one on
        first contact. Returns None if this participant is a marked spectator,
        or once two distinct (non-spectator) participants already hold X and O."""
        if participant_id in self.spectator_ids:
            return None
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
        self.spectator_ids.discard(participant_id)

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
