import pytest

from games.tictactoe import WINNING_LINES, TicTacToe


def _win_via_line(line: tuple[int, int, int], winner: str = "X") -> TicTacToe:
    """Play a legal game ending in `winner` completing `line`. The winner's
    third cell is always played last so no accidental second win can form
    from the loser's filler moves (mirrors how a real game halts on a win)."""
    game = TicTacToe()
    loser = "O" if winner == "X" else "X"
    other_cells = [i for i in range(9) if i not in line]
    game.apply_move(winner, line[0])
    game.apply_move(loser, other_cells[0])
    game.apply_move(winner, line[1])
    game.apply_move(loser, other_cells[1])
    game.apply_move(winner, line[2])
    return game


@pytest.mark.parametrize("line", WINNING_LINES)
@pytest.mark.parametrize("winner", ["X", "O"])
def test_every_winning_line_is_detected(line: tuple[int, int, int], winner: str) -> None:
    game = _win_via_line(line, winner)
    assert game.is_game_over() == winner


def test_initial_state_has_no_winner() -> None:
    game = TicTacToe()
    assert game.is_game_over() is None
    assert game.get_state() == {"board": [None] * 9}


def test_get_valid_moves_shrinks_as_cells_are_played() -> None:
    game = TicTacToe()
    assert game.get_valid_moves() == list(range(9))
    game.apply_move("X", 4)
    assert 4 not in game.get_valid_moves()
    assert len(game.get_valid_moves()) == 8


def test_draw_when_board_full_with_no_winner() -> None:
    game = TicTacToe()
    # X O X
    # X O O
    # O X X
    moves = [("X", 0), ("O", 1), ("X", 2), ("O", 4), ("X", 3), ("O", 5), ("X", 7), ("O", 6), ("X", 8)]
    for player, cell in moves:
        assert game.apply_move(player, cell) is True
    assert game.is_game_over() == "draw"


def test_apply_move_rejects_occupied_cell() -> None:
    game = TicTacToe()
    assert game.apply_move("X", 0) is True
    assert game.apply_move("O", 0) is False
    assert game.get_state()["board"][0] == "X"


@pytest.mark.parametrize("out_of_bounds_move", [-1, 9, 100])
def test_apply_move_rejects_out_of_bounds(out_of_bounds_move: int) -> None:
    game = TicTacToe()
    assert game.apply_move("X", out_of_bounds_move) is False


def test_apply_move_rejects_non_integer_move() -> None:
    game = TicTacToe()
    assert game.apply_move("X", "4") is False
    assert game.apply_move("X", None) is False


def test_game_over_returns_none_mid_game() -> None:
    game = TicTacToe()
    game.apply_move("X", 0)
    game.apply_move("O", 4)
    assert game.is_game_over() is None
