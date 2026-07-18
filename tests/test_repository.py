import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from server.database import Base, engine, async_session_maker
from server.repository import ArenaRepository
from server.models import MatchStatus

import pytest_asyncio

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    # Recreate tables for every test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_repository_crud():
    async with async_session_maker() as session:
        repo = ArenaRepository(session)
        
        # Test create_match
        match = await repo.create_match()
        assert match.id is not None
        assert match.status == MatchStatus.PENDING
        
        # Test get_match
        fetched = await repo.get_match(match.id)
        assert fetched is not None
        assert fetched.id == match.id
        
        # Test update_match_status
        updated = await repo.update_match_status(match.id, MatchStatus.ACTIVE)
        assert updated.status == MatchStatus.ACTIVE
        
        # Test log_move
        move = await repo.log_move(match.id, "player_x", {"cell": 4})
        assert move.match_id == match.id
        assert move.player_id == "player_x"
        assert move.move_payload == {"cell": 4}
        
        # Test get_moves
        moves = await repo.get_moves(match.id)
        assert len(moves) == 1
        assert moves[0].id == move.id
        
        # Test log_chat
        chat = await repo.log_chat(match.id, "player_y", "Hello, World!")
        assert chat.match_id == match.id
        assert chat.sender == "player_y"
        assert chat.message == "Hello, World!"
        
        # Test get_chats
        chats = await repo.get_chats(match.id)
        assert len(chats) == 1
        assert chats[0].id == chat.id
