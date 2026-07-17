import pytest
from sqlalchemy import text
from server.database import engine, Base

@pytest.mark.asyncio
async def test_engine_initialization():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        res = await conn.execute(text("SELECT 1"))
        assert res.scalar() == 1
