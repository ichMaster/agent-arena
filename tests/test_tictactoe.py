"""Exhaustive unit tests for the TicTacToe engine (roadmap §v01.01 Tests).

Pure logic — no server, no LLM, no paid call. Covers: win on every one of the 8 lines, draw
detection, illegal-move rejection per category (out-of-range, occupied, wrong-type) without
raising, and that ``get_valid_moves`` shrinks correctly.
"""

import pytest

from games.interface import GameInterface
from games.tictactoe import BOARD_SIZE, TicTacToe

# The 8 winning lines, enumerated independently of the engine so this is a real cross-check
# (if the engine ever drops or mangles a line, these parametrized cases catch it).
ALL_WINNING_LINES: list[tuple[int, int, int]] = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),   # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),   # columns
    (0, 4, 8), (2, 4, 6),              # diagonals
]

EMPTY_BOARD = {"board": [""] * BOARD_SIZE}


def test_is_a_game_interface() -> None:
    assert isinstance(TicTacToe(), GameInterface)


def test_fresh_board_is_empty_and_ongoing() -> None:
    game = TicTacToe()
    assert game.get_state() == EMPTY_BOARD
    assert game.get_valid_moves() == list(range(BOARD_SIZE))
    assert game.is_game_over() is None


@pytest.mark.parametrize("line", ALL_WINNING_LINES)
def test_win_on_every_line(line: tuple[int, int, int]) -> None:
    fillers = [cell for cell in range(BOARD_SIZE) if cell not in line]
    game = TicTacToe()
    # Interleave so X completes the line on its third move; O only ever holds 2 cells (can't win).
    assert game.apply_move("X", line[0]) is True
    assert game.apply_move("O", fillers[0]) is True
    assert game.is_game_over() is None
    assert game.apply_move("X", line[1]) is True
    assert game.apply_move("O", fillers[1]) is True
    assert game.is_game_over() is None
    assert game.apply_move("X", line[2]) is True
    assert game.is_game_over() == "X"
    assert game.get_valid_moves() == []


def test_o_can_win_too() -> None:
    game = TicTacToe()
    # O completes the right column (2, 5, 8); X scattered and never lines up.
    for player, cell in [("X", 0), ("O", 2), ("X", 1), ("O", 5), ("X", 4), ("O", 8)]:
        assert game.apply_move(player, cell) is True
    assert game.is_game_over() == "O"


def test_draw_detection() -> None:
    game = TicTacToe()
    # Final board:  X O X / X O O / O X X  -> full, no line.
    sequence = [
        ("X", 0), ("O", 1), ("X", 2),
        ("O", 4), ("X", 3), ("O", 5),
        ("X", 7), ("O", 6), ("X", 8),
    ]
    for index, (player, cell) in enumerate(sequence):
        assert game.apply_move(player, cell) is True
        if index < len(sequence) - 1:
            assert game.is_game_over() is None  # no premature win along the way
    assert game.is_game_over() == "draw"
    assert game.get_valid_moves() == []


@pytest.mark.parametrize("bad_move", [BOARD_SIZE, 9, 10, 100, -1, -100])
def test_out_of_range_moves_rejected(bad_move: int) -> None:
    game = TicTacToe()
    assert game.apply_move("X", bad_move) is False
    assert game.get_state() == EMPTY_BOARD  # board unchanged
    assert len(game.get_valid_moves()) == BOARD_SIZE


def test_occupied_cell_rejected() -> None:
    game = TicTacToe()
    assert game.apply_move("X", 4) is True
    assert game.apply_move("O", 4) is False  # occupied by X
    assert game.apply_move("X", 4) is False  # still occupied
    assert game.get_state()["board"][4] == "X"
    assert len(game.get_valid_moves()) == BOARD_SIZE - 1


@pytest.mark.parametrize("bad_move", ["0", "4", 1.5, 3.0, None, True, False, [0], (0,)])
def test_wrong_type_moves_rejected(bad_move: object) -> None:
    game = TicTacToe()
    assert game.apply_move("X", bad_move) is False
    assert game.get_state() == EMPTY_BOARD


def test_illegal_moves_never_raise() -> None:
    game = TicTacToe()
    for bad in [9, -1, "x", 1.5, None, True, [0], (1, 2)]:
        # The sole legality authority returns False; it must never raise on bad input.
        assert game.apply_move("X", bad) is False


def test_unknown_player_rejected() -> None:
    game = TicTacToe()
    assert game.apply_move("Z", 0) is False
    assert game.apply_move("x", 0) is False  # symbols are case-sensitive
    assert game.get_state() == EMPTY_BOARD


def test_get_valid_moves_shrinks_by_one_each_move() -> None:
    game = TicTacToe()
    expected = list(range(BOARD_SIZE))
    assert game.get_valid_moves() == expected
    for player, cell in [("X", 0), ("O", 8), ("X", 4), ("O", 2)]:
        assert game.apply_move(player, cell) is True
        expected.remove(cell)
        assert game.get_valid_moves() == expected
        assert cell not in game.get_valid_moves()


def test_no_moves_accepted_after_game_over() -> None:
    game = TicTacToe()
    for player, cell in [("X", 0), ("O", 3), ("X", 1), ("O", 4), ("X", 2)]:  # X wins top row
        assert game.apply_move(player, cell) is True
    assert game.is_game_over() == "X"
    assert game.apply_move("O", 5) is False  # game already decided
    assert game.get_valid_moves() == []


def test_get_state_returns_a_copy() -> None:
    game = TicTacToe()
    state = game.get_state()
    state["board"][0] = "X"  # mutate the returned copy
    assert game.get_state()["board"][0] == ""  # authoritative state untouched
