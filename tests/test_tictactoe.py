"""Exhaustive unit tests for the TicTacToe engine (roadmap §v01.01 Tests).

Pure logic, no server, no LLM, no paid call: win on every one of the 8 lines, draw detection,
illegal-move rejection per category (never raising), and the get_valid_moves shrink invariant.
"""

import pytest

from games.tictactoe import TicTacToe, _WINNING_LINES


def _play(game: TicTacToe, moves: list[tuple[str, int]]) -> None:
    for player, cell in moves:
        assert game.apply_move(player, cell) is True


def test_new_game_state() -> None:
    game = TicTacToe()
    assert game.get_state() == {"board": [""] * 9}
    assert game.get_valid_moves() == list(range(9))
    assert game.is_game_over() is None


@pytest.mark.parametrize("line", _WINNING_LINES)
def test_win_on_every_line(line: tuple[int, int, int]) -> None:
    """X wins on `line`; O plays cells outside it (and outside any accidental O-line)."""
    game = TicTacToe()
    o_cells = [i for i in range(9) if i not in line]
    for i, x_cell in enumerate(line):
        assert game.apply_move("X", x_cell) is True
        if game.is_game_over() is not None:
            break  # the third X completes the line
        assert game.apply_move("O", o_cells[i]) is True
    assert game.is_game_over() == "X"
    assert game.get_valid_moves() == []  # terminal: no more legal moves


def test_draw_on_full_board_with_no_line() -> None:
    # X O X / X O O / O X X — full, no three-in-a-row.
    board = [
        ("X", 0), ("O", 1), ("X", 2),
        ("X", 3), ("O", 4), ("O", 5),
        ("O", 6), ("X", 7), ("X", 8),
    ]
    game = TicTacToe()
    _play(game, board)
    assert game.is_game_over() == "draw"
    assert game.get_valid_moves() == []


def test_reject_out_of_range() -> None:
    game = TicTacToe()
    for bad in (-1, 9, 100):
        assert game.apply_move("X", bad) is False
    assert game.get_state() == {"board": [""] * 9}  # nothing marked


def test_reject_occupied_cell() -> None:
    game = TicTacToe()
    assert game.apply_move("X", 4) is True
    assert game.apply_move("O", 4) is False  # already taken


def test_reject_wrong_type_never_raises() -> None:
    game = TicTacToe()
    for bad in ("4", 4.0, None, [4], True, False):
        assert game.apply_move("X", bad) is False


def test_reject_unknown_player() -> None:
    game = TicTacToe()
    assert game.apply_move("Z", 0) is False


def test_valid_moves_shrink_as_board_fills() -> None:
    game = TicTacToe()
    assert len(game.get_valid_moves()) == 9
    game.apply_move("X", 0)
    assert 0 not in game.get_valid_moves()
    assert len(game.get_valid_moves()) == 8
    game.apply_move("O", 8)
    assert set(game.get_valid_moves()) == {1, 2, 3, 4, 5, 6, 7}


def test_no_moves_accepted_after_game_over() -> None:
    game = TicTacToe()
    _play(game, [("X", 0), ("O", 3), ("X", 1), ("O", 4), ("X", 2)])  # X wins top row
    assert game.is_game_over() == "X"
    assert game.apply_move("O", 5) is False  # game already decided
