import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import IntegrityError
from server.database import Base
from server.repository import Repository
from server.models import MatchModel, MoveLogModel, ChatLogModel
import uuid

@pytest_asyncio.fixture
async def async_db_session():
    # In-memory async sqlite
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    from sqlalchemy import event
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session

@pytest.mark.asyncio
async def test_repository_crud(async_db_session):
    repo = Repository(async_db_session)
    match_id = str(uuid.uuid4())
    
    # Test insert match
    match = await repo.insert_match(match_id)
    assert match.id == match_id
    assert match.status == "PENDING"
    
    # Test fetch match
    fetched = await repo.fetch_match(match_id)
    assert fetched is not None
    assert fetched.id == match_id
    
    # Test log move
    move = await repo.log_move(match_id, "player1", {"x": 1})
    assert move.match_id == match_id
    assert move.player_id == "player1"
    
    # Test log chat
    chat = await repo.log_chat_message(match_id, "player1", "Hello!")
    assert chat.match_id == match_id
    assert chat.message == "Hello!"
    
    # Test fetch moves and chats
    moves = await repo.fetch_move_logs(match_id)
    assert len(moves) == 1
    
    chats = await repo.fetch_chat_logs(match_id)
    assert len(chats) == 1

@pytest.mark.asyncio
async def test_foreign_key_constraint(async_db_session):
    repo = Repository(async_db_session)
    
    # Try inserting move for non-existent match
    with pytest.raises(IntegrityError):
        await repo.log_move("invalid-match", "player1", {"x": 1})
