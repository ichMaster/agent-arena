import pytest
from server.database import Base, engine
from server.models import MatchModel, MoveLogModel, ChatLogModel

@pytest.mark.asyncio
async def test_schema_creation():
    # Verify we can build all tables defined in models.py
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Check that table names are registered correctly
    assert "matches" in Base.metadata.tables
    assert "move_logs" in Base.metadata.tables
    assert "chat_logs" in Base.metadata.tables
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
