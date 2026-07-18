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
