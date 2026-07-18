import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from server.database import Base
from server.repository import Repository


@pytest.fixture
async def repository():
    memory_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with memory_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(memory_engine, expire_on_commit=False)
    async with session_maker() as session:
        yield Repository(session)
    await memory_engine.dispose()
