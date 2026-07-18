import pytest
from games.tictactoe import TicTacToe

def test_initial_state():
    game = TicTacToe()
    assert game.get_valid_moves() == list(range(9))
    assert game.is_game_over() is None

def test_apply_move():
    game = TicTacToe()
    assert game.apply_move("X", 0) is True
    assert game.get_state()["board"][0] == "X"
    assert game.get_state()["current_turn"] == "O"

def test_invalid_moves():
    game = TicTacToe()
    # out of bounds
    assert game.apply_move("X", 9) is False
    assert game.apply_move("X", -1) is False
    # wrong type
    assert game.apply_move("X", "0") is False
    # wrong turn
    assert game.apply_move("O", 0) is False
    # cell already occupied
    game.apply_move("X", 0)
    assert game.apply_move("O", 0) is False

def test_win_rows():
    for row in range(3):
        game = TicTacToe()
        for i in range(3):
            if i > 0:
                game.apply_move("O", (row + 1) % 3 * 3 + i - 1)
            game.apply_move("X", row * 3 + i)
        assert game.is_game_over() == "X"

def test_win_cols():
    for col in range(3):
        game = TicTacToe()
        for i in range(3):
            if i > 0:
                game.apply_move("O", (col + 1) % 3 + (i - 1) * 3)
            game.apply_move("X", col + i * 3)
        assert game.is_game_over() == "X"

def test_win_diags():
    game = TicTacToe()
    game.apply_move("X", 0)
    game.apply_move("O", 1)
    game.apply_move("X", 4)
    game.apply_move("O", 2)
    game.apply_move("X", 8)
    assert game.is_game_over() == "X"
    
    game = TicTacToe()
    game.apply_move("X", 2)
    game.apply_move("O", 1)
    game.apply_move("X", 4)
    game.apply_move("O", 0)
    game.apply_move("X", 6)
    assert game.is_game_over() == "X"

def test_draw():
    game = TicTacToe()
    # 0:X, 1:O, 2:X, 4:O, 3:X, 5:O, 7:X, 6:O, 8:X
    moves = [0, 1, 2, 4, 3, 5, 7, 6, 8]
    for i, move in enumerate(moves):
        player = "X" if i % 2 == 0 else "O"
        game.apply_move(player, move)
        
    assert game.is_game_over() == "draw"

def test_moves_after_game_over():
    game = TicTacToe()
    game.apply_move("X", 0)
    game.apply_move("O", 3)
    game.apply_move("X", 1)
    game.apply_move("O", 4)
    game.apply_move("X", 2)
    assert game.is_game_over() == "X"
    assert game.apply_move("O", 5) is False
    assert len(game.get_valid_moves()) == 0
