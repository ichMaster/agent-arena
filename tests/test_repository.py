import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from server.database import engine, Base, async_session_maker
from server.repository import ArenaRepository
from server.models import MatchStatus

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_repository_crud():
    async with async_session_maker() as session:
        repo = ArenaRepository(session)
        
        # Test Create Match
        match = await repo.create_match()
        assert match is not None
        assert match.id is not None
        assert match.status == MatchStatus.PENDING
        
        # Test Get Match
        fetched_match = await repo.get_match(match.id)
        assert fetched_match is not None
        assert fetched_match.id == match.id
        
        # Test Log Move
        move = await repo.log_move(match.id, "player1", {"x": 1, "y": 2})
        assert move is not None
        assert move.player_id == "player1"
        assert move.move_payload == {"x": 1, "y": 2}
        
        # Test Get Moves
        moves = await repo.get_moves(match.id)
        assert len(moves) == 1
        assert moves[0].id == move.id
        
        # Test Log Chat
        chat = await repo.log_chat(match.id, "player2", "Hello World")
        assert chat is not None
        assert chat.sender == "player2"
        assert chat.message == "Hello World"
        
        # Test Get Chat
        chats = await repo.get_chat(match.id)
        assert len(chats) == 1
        assert chats[0].id == chat.id

@pytest.mark.asyncio
async def test_foreign_key_constraint():
    async with async_session_maker() as session:
        repo = ArenaRepository(session)
        
        with pytest.raises(IntegrityError):
            await repo.log_move("fake-match-id", "player1", {})
