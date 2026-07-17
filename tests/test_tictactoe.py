import pytest
from games.tictactoe import TicTacToe

def test_initial_state():
    game = TicTacToe()
    state = game.get_state()
    assert state["board"] == [None] * 9
    assert state["current_turn"] == 'X'
    assert state["status"] is None
    assert game.get_valid_moves() == list(range(9))

def test_apply_valid_move():
    game = TicTacToe()
    assert game.apply_move('X', 4) is True
    assert game.board[4] == 'X'
    assert game.current_turn == 'O'
    assert 4 not in game.get_valid_moves()
    
    assert game.apply_move('O', 0) is True
    assert game.board[0] == 'O'
    assert game.current_turn == 'X'

def test_apply_invalid_moves():
    game = TicTacToe()
    # Wrong player
    assert game.apply_move('O', 4) is False
    
    # Invalid move types/bounds
    assert game.apply_move('X', -1) is False
    assert game.apply_move('X', 9) is False
    assert game.apply_move('X', "middle") is False
    
    # Valid move for X
    assert game.apply_move('X', 4) is True
    
    # Colliding move for O
    assert game.apply_move('O', 4) is False
    # State should remain unchanged
    assert game.board[4] == 'X'
    assert game.current_turn == 'O'

@pytest.mark.parametrize("winning_moves,winner", [
    # Rows
    ([0, 3, 1, 4, 2], 'X'),
    ([3, 0, 4, 1, 5], 'X'),
    ([6, 0, 7, 1, 8], 'X'),
    # Cols
    ([0, 1, 3, 2, 6], 'X'),
    ([1, 0, 4, 2, 7], 'X'),
    ([2, 0, 5, 1, 8], 'X'),
    # Diagonals
    ([0, 1, 4, 2, 8], 'X'),
    ([2, 0, 4, 1, 6], 'X'),
])
def test_win_conditions_for_X(winning_moves, winner):
    game = TicTacToe()
    current_player = 'X'
    for move in winning_moves:
        assert game.apply_move(current_player, move) is True
        current_player = 'O' if current_player == 'X' else 'X'
    assert game.is_game_over() == winner

def test_win_condition_for_O():
    game = TicTacToe()
    # X plays 0, O plays 3, X plays 1, O plays 4, X plays 8, O plays 5 (O wins)
    moves = [0, 3, 1, 4, 8, 5]
    current_player = 'X'
    for move in moves:
        assert game.apply_move(current_player, move) is True
        current_player = 'O' if current_player == 'X' else 'X'
    assert game.is_game_over() == 'O'

def test_draw_condition():
    game = TicTacToe()
    # A standard draw game
    # X O X
    # X O O
    # O X X
    moves = [0, 1, 2, 4, 3, 5, 7, 6, 8]
    current_player = 'X'
    for move in moves:
        assert game.apply_move(current_player, move) is True
        current_player = 'O' if current_player == 'X' else 'X'
    
    assert game.is_game_over() == 'draw'
    assert game.get_valid_moves() == []
