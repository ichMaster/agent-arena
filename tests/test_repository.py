import uuid

import pytest
from sqlalchemy.exc import IntegrityError
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


async def test_create_and_get_match(repository: Repository) -> None:
    match_id = str(uuid.uuid4())
    await repository.create_match(match_id)
    fetched = await repository.get_match(match_id)
    assert fetched is not None
    assert fetched.id == match_id


async def test_log_and_fetch_moves(repository: Repository) -> None:
    match_id = str(uuid.uuid4())
    await repository.create_match(match_id)
    await repository.log_move(match_id, player_id="X", move_payload={"cell": 4})
    logs = await repository.get_move_logs(match_id)
    assert len(logs) == 1
    assert logs[0].move_payload == {"cell": 4}


async def test_log_and_fetch_chat(repository: Repository) -> None:
    match_id = str(uuid.uuid4())
    await repository.create_match(match_id)
    await repository.log_chat(match_id, sender="Ada", message="gg")
    logs = await repository.get_chat_logs(match_id)
    assert len(logs) == 1
    assert logs[0].message == "gg"


async def test_move_log_rejects_nonexistent_match_id(repository: Repository) -> None:
    with pytest.raises(IntegrityError):
        await repository.log_move(str(uuid.uuid4()), player_id="X", move_payload={"cell": 0})
