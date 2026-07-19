"""Tests for reconstruct_game + current_turn (architecture §5.1) — rebuild state by replay.

Logs moves through the Repository, then checks the reconstructed board / whose-turn / result for an
empty match, an ongoing game, a win, and a draw. Throwaway DB, no LLM, no paid call.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from server.repository import Repository

EMPTY_BOARD = {"board": [""] * 9}


async def test_reconstruct_empty_match(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        game = await repo.reconstruct_game("m1")
        assert game.get_state() == EMPTY_BOARD
        assert game.is_game_over() is None
        assert await repo.current_turn("m1") == "X"  # 0 moves -> X


async def test_reconstruct_ongoing_board_and_turn(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        for symbol, cell in [("X", 0), ("O", 4)]:
            await repo.log_move("m1", symbol, cell)
        game = await repo.reconstruct_game("m1")
        board = game.get_state()["board"]
        assert board[0] == "X" and board[4] == "O"
        assert game.is_game_over() is None
        assert await repo.current_turn("m1") == "X"  # 2 moves -> X


async def test_current_turn_alternates_by_parity(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        assert await repo.current_turn("m1") == "X"  # 0
        await repo.log_move("m1", "X", 0)
        assert await repo.current_turn("m1") == "O"  # 1
        await repo.log_move("m1", "O", 4)
        assert await repo.current_turn("m1") == "X"  # 2


async def test_reconstruct_win_current_turn_none(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        for symbol, cell in [("X", 0), ("O", 3), ("X", 1), ("O", 4), ("X", 2)]:  # X wins top row
            await repo.log_move("m1", symbol, cell)
        game = await repo.reconstruct_game("m1")
        assert game.is_game_over() == "X"
        assert await repo.current_turn("m1") is None  # game over -> no turn


async def test_reconstruct_draw_current_turn_none(
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        repo = Repository(session)
        await repo.create_match("m1")
        draw = [("X", 0), ("O", 1), ("X", 2), ("O", 4), ("X", 3), ("O", 5), ("X", 7), ("O", 6), ("X", 8)]
        for symbol, cell in draw:
            await repo.log_move("m1", symbol, cell)
        game = await repo.reconstruct_game("m1")
        assert game.is_game_over() == "draw"
        assert await repo.current_turn("m1") is None
