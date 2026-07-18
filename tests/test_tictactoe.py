from games.tictactoe import TicTacToe

def test_tictactoe_initial_state():
    game = TicTacToe()
    assert game.get_state() == {
        "board": [None] * 9,
        "current_turn": "X",
        "status": "ACTIVE"
    }
    assert game.get_valid_moves() == list(range(9))
    assert game.is_game_over() is None

def test_tictactoe_apply_valid_move():
    game = TicTacToe()
    assert game.apply_move("X", 4) is True
    assert game.board[4] == "X"
    assert game.current_turn == "O"
    assert 4 not in game.get_valid_moves()

def test_tictactoe_apply_invalid_move():
    game = TicTacToe()
    assert game.apply_move("X", 4) is True
    # Duplicate move fails
    assert game.apply_move("O", 4) is False
    # Out of turn fails
    assert game.apply_move("X", 0) is False
    # Out of bounds fails
    assert game.apply_move("O", -1) is False
    assert game.apply_move("O", 9) is False
    assert game.apply_move("O", "invalid") is False

def test_tictactoe_row_wins():
    # Play X and O alternately
    # Row 0:
    # X: 0, O: 3, X: 1, O: 4, X: 2
    game = TicTacToe()
    game.apply_move("X", 0)
    game.apply_move("O", 3)
    game.apply_move("X", 1)
    game.apply_move("O", 4)
    assert game.is_game_over() is None
    game.apply_move("X", 2)
    assert game.is_game_over() == "X"

def test_tictactoe_col_wins():
    # Col 0:
    # X: 0, O: 1, X: 3, O: 4, X: 5, O: 7 (wait: O wants 1, 4, 7)
    # X: 0, O: 1, X: 3, O: 4, X: 2, O: 7
    game = TicTacToe()
    game.apply_move("X", 0) # X
    game.apply_move("O", 1) # O
    game.apply_move("X", 3) # X
    game.apply_move("O", 4) # O
    game.apply_move("X", 2) # X
    assert game.is_game_over() is None
    game.apply_move("O", 7) # O
    assert game.is_game_over() == "O"

def test_tictactoe_diag_wins():
    # Diagonal 1: 0, 4, 8
    # X: 0, O: 1, X: 4, O: 2, X: 8
    game = TicTacToe()
    game.apply_move("X", 0)
    game.apply_move("O", 1)
    game.apply_move("X", 4)
    game.apply_move("O", 2)
    assert game.is_game_over() is None
    game.apply_move("X", 8)
    assert game.is_game_over() == "X"

    # Diagonal 2: 2, 4, 6 (winner O)
    # X: 0, O: 2, X: 1, O: 4, X: 3, O: 6
    game = TicTacToe()
    game.apply_move("X", 0)
    game.apply_move("O", 2)
    game.apply_move("X", 1)
    game.apply_move("O", 4)
    game.apply_move("X", 3)
    assert game.is_game_over() is None
    game.apply_move("O", 6)
    assert game.is_game_over() == "O"

def test_tictactoe_draw():
    game = TicTacToe()
    # Fill the board in a way that leads to a draw:
    # X O X
    # X O O
    # O X X
    # X:0, O:1, X:2, O:4, X:3, O:5, X:7, O:6, X:8 (alternate turns)
    moves = [
        ("X", 0), ("O", 1), ("X", 2),
        ("O", 4), ("X", 3), ("O", 5),
        ("X", 7), ("O", 6), ("X", 8)
    ]
    for p, cell in moves:
        assert game.apply_move(p, cell) is True
        
    assert game.is_game_over() == "draw"
