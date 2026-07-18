from sqlalchemy.ext.asyncio import create_async_engine

from server.database import Base, init_models


async def test_init_models_creates_schema_in_memory() -> None:
    memory_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_models(bind_engine=memory_engine)
    async with memory_engine.begin() as conn:
        table_names = await conn.run_sync(lambda sync_conn: Base.metadata.tables.keys())
    assert table_names is not None
    await memory_engine.dispose()
