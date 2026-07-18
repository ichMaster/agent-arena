from server.match import Match, clear_match, get_or_create_match, release_participant


def test_assign_symbol_gives_first_two_distinct_participants_x_then_o() -> None:
    match = Match("m1")
    assert match.assign_symbol("token-ada") == "X"
    assert match.assign_symbol("token-bob") == "O"


def test_assign_symbol_is_idempotent_for_the_same_participant() -> None:
    match = Match("m1")
    assert match.assign_symbol("token-ada") == "X"
    assert match.assign_symbol("token-ada") == "X"


def test_assign_symbol_returns_none_for_a_third_participant() -> None:
    match = Match("m1")
    match.assign_symbol("token-ada")
    match.assign_symbol("token-bob")
    assert match.assign_symbol("token-cara") is None


def test_two_participants_with_the_same_display_name_get_different_seats() -> None:
    """Regression for the seat-collision bug: seats are keyed by a unique
    participant_id (the auth token), not the player's chosen display name —
    the Web UI defaults every session's name prompt to "Human", so two
    different people accepting that default must not end up sharing a seat."""
    match = Match("m1")
    # Two distinct sessions, both happen to display as "Human" — but they're
    # identified by two distinct participant_ids (tokens), same as in prod.
    first_seat = match.assign_symbol("token-for-session-1")
    second_seat = match.assign_symbol("token-for-session-2")
    assert first_seat != second_seat
    assert {first_seat, second_seat} == {"X", "O"}


def test_release_seat_frees_it_for_a_new_participant() -> None:
    match = Match("m1")
    match.assign_symbol("token-ada")
    match.assign_symbol("token-bob")
    assert match.assign_symbol("token-cara") is None  # no seats left

    match.release_seat("token-ada")
    assert match.assign_symbol("token-cara") == "X"  # Ada's old seat is reclaimed


def test_release_seat_is_a_no_op_for_an_unknown_participant() -> None:
    match = Match("m1")
    match.assign_symbol("token-ada")
    match.release_seat("token-never-joined")  # must not raise
    assert match.assign_symbol("token-ada") == "X"  # Ada's seat untouched


def test_release_participant_updates_the_active_match_registry() -> None:
    match_id = "release-participant-test"
    try:
        match = get_or_create_match(match_id)
        match.assign_symbol("token-ada")
        match.assign_symbol("token-bob")
        assert match.assign_symbol("token-cara") is None

        release_participant(match_id, "token-ada")
        assert match.assign_symbol("token-cara") == "X"
    finally:
        clear_match(match_id)


def test_release_participant_on_unknown_match_does_not_raise() -> None:
    release_participant("no-such-match", "token-ada")


def test_mark_spectator_permanently_prevents_assign_symbol() -> None:
    """Regression: a spectator who joins before the match fills up must never
    accidentally BECOME one of the two players — a real swarm run had exactly
    this happen when a browser session used "Join Match" (a real player join)
    instead of a genuine spectate action, starving one of the two launched
    agents of a seat entirely."""
    match = Match("m1")
    match.mark_spectator("token-spectator")
    assert match.assign_symbol("token-spectator") is None
    # The seat isn't just skipped for the spectator — it's still free for
    # real players, i.e. marking a spectator doesn't waste one of the 2 seats.
    assert match.assign_symbol("token-ada") == "X"
    assert match.assign_symbol("token-bob") == "O"


def test_mark_spectator_after_already_holding_a_seat_does_not_retroactively_apply() -> None:
    # Only relevant if a caller marks spectator status before ever calling
    # assign_symbol for that participant_id (the real WS handshake always
    # does this in that order) — documented here so the ordering dependency
    # is explicit rather than implicit.
    match = Match("m1")
    match.assign_symbol("token-ada")
    match.mark_spectator("token-ada")
    assert match.assign_symbol("token-ada") == "X"  # already-held seat is not revoked


def test_release_seat_also_clears_spectator_status() -> None:
    match = Match("m1")
    match.mark_spectator("token-spectator")
    match.release_seat("token-spectator")
    # Not marked as a spectator anymore — a fresh connection reusing this
    # participant_id (unlikely in practice, but the state shouldn't linger)
    # can now be assigned a real seat.
    assert match.assign_symbol("token-spectator") == "X"
