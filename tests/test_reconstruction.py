"""Move-log reconstruction tests (ARENA-OPUS-OPUS-007). Throwaway DB, no LLM, no paid call.

Confirms the board / current_turn / result are derived purely by replaying the persisted move log,
for an ongoing game, a win, and a draw.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

from server.database import create_engine, create_session_maker, init_models
from server.repository import Repository


@pytest_asyncio.fixture
async def repo(tmp_path: Path) -> AsyncIterator[Repository]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/arena.db")
    await init_models(engine)
    maker = create_session_maker(engine)
    async with maker() as session:
        yield Repository(session)
    await engine.dispose()


async def _log(repo: Repository, match_id: str, moves: list[tuple[str, int]]) -> None:
    for symbol, cell in moves:
        await repo.log_move(match_id, symbol, cell)


async def test_empty_match_reconstructs_to_new_board(repo: Repository) -> None:
    await repo.create_match("m1")
    game = await repo.reconstruct_game("m1")
    assert game.get_state() == {"board": [""] * 9}
    assert await repo.current_turn("m1") == "X"  # X moves first


async def test_ongoing_game_board_and_turn(repo: Repository) -> None:
    await repo.create_match("m1")
    await _log(repo, "m1", [("X", 4), ("O", 0)])
    game = await repo.reconstruct_game("m1")
    board = game.get_state()["board"]
    assert board[4] == "X" and board[0] == "O"
    assert await repo.current_turn("m1") == "X"  # 2 moves logged -> X again


async def test_win_reconstructs_result_and_null_turn(repo: Repository) -> None:
    await repo.create_match("m1")
    # X: 0,1,2 top row; O: 3,4 between.
    await _log(repo, "m1", [("X", 0), ("O", 3), ("X", 1), ("O", 4), ("X", 2)])
    game = await repo.reconstruct_game("m1")
    assert game.is_game_over() == "X"
    assert await repo.current_turn("m1") is None  # terminal -> no turn


async def test_draw_reconstructs_and_null_turn(repo: Repository) -> None:
    await repo.create_match("m1")
    # X O X / X O O / O X X — full, no line.
    await _log(
        repo,
        "m1",
        [("X", 0), ("O", 1), ("X", 2), ("X", 3), ("O", 4), ("O", 5), ("O", 6), ("X", 7), ("X", 8)],
    )
    game = await repo.reconstruct_game("m1")
    assert game.is_game_over() == "draw"
    assert await repo.current_turn("m1") is None


async def test_turn_is_null_on_and_after_the_terminal_move(repo: Repository) -> None:
    await repo.create_match("m1")
    await _log(repo, "m1", [("X", 0), ("O", 3), ("X", 1), ("O", 4)])
    assert await repo.current_turn("m1") == "X"  # X's winning move is next
    await repo.log_move("m1", "X", 2)  # the terminal move
    assert await repo.current_turn("m1") is None
