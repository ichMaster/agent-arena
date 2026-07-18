import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from server.database import Base, engine, async_session_maker

@pytest.mark.asyncio
async def test_engine_initialization():
    # Make sure we can connect and bind the engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Make sure we can create an async session
    async with async_session_maker() as session:
        assert isinstance(session, AsyncSession)
        
    # Cleanup tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
