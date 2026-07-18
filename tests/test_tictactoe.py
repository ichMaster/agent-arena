from games.tictactoe import TicTacToe

def test_tictactoe_initial_state():
    game = TicTacToe()
    assert game.get_state() == {"board": [None] * 9}
    assert game.get_valid_moves() == list(range(9))
    assert game.is_game_over() is None

def test_tictactoe_apply_valid_move():
    game = TicTacToe()
    assert game.apply_move("X", 4) is True
    assert game.board[4] == "X"
    assert 4 not in game.get_valid_moves()

def test_tictactoe_apply_invalid_move():
    game = TicTacToe()
    assert game.apply_move("X", 4) is True
    # Duplicate move fails
    assert game.apply_move("O", 4) is False
    # Out of bounds fails
    assert game.apply_move("O", -1) is False
    assert game.apply_move("O", 9) is False
    assert game.apply_move("O", "invalid") is False

def test_tictactoe_row_wins():
    for row in range(3):
        game = TicTacToe()
        cells = [row * 3, row * 3 + 1, row * 3 + 2]
        game.apply_move("X", cells[0])
        game.apply_move("X", cells[1])
        assert game.is_game_over() is None
        game.apply_move("X", cells[2])
        assert game.is_game_over() == "X"

def test_tictactoe_col_wins():
    for col in range(3):
        game = TicTacToe()
        cells = [col, col + 3, col + 6]
        game.apply_move("O", cells[0])
        game.apply_move("O", cells[1])
        assert game.is_game_over() is None
        game.apply_move("O", cells[2])
        assert game.is_game_over() == "O"

def test_tictactoe_diag_wins():
    # Diagonal 1
    game = TicTacToe()
    game.apply_move("X", 0)
    game.apply_move("X", 4)
    assert game.is_game_over() is None
    game.apply_move("X", 8)
    assert game.is_game_over() == "X"

    # Diagonal 2
    game = TicTacToe()
    game.apply_move("O", 2)
    game.apply_move("O", 4)
    assert game.is_game_over() is None
    game.apply_move("O", 6)
    assert game.is_game_over() == "O"

def test_tictactoe_draw():
    game = TicTacToe()
    # Fill the board in a way that leads to a draw
    # X O X
    # X O O
    # O X X
    moves = [
        ("X", 0), ("O", 1), ("X", 2),
        ("X", 3), ("O", 4), ("O", 5),
        ("O", 6), ("X", 7), ("X", 8)
    ]
    for p, cell in moves:
        game.apply_move(p, cell)
        
    assert game.is_game_over() == "Draw"
