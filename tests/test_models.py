import pytest
from server.database import engine, Base
from server.models import MatchModel, MoveLogModel, ChatLogModel

@pytest.mark.asyncio
async def test_schema_creation():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    assert True
