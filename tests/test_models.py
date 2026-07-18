from sqlalchemy.ext.asyncio import create_async_engine

from server.database import Base, init_models
from server.models import ChatLogModel, MatchModel, MatchStatus, MoveLogModel


async def test_schema_creates_without_errors() -> None:
    memory_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_models(bind_engine=memory_engine)
    table_names = set(Base.metadata.tables.keys())
    assert table_names == {"matches", "move_logs", "chat_logs"}
    await memory_engine.dispose()


def test_match_status_enum_values() -> None:
    assert {s.value for s in MatchStatus} == {"PENDING", "ACTIVE", "COMPLETED"}


def test_models_declare_expected_columns() -> None:
    assert "match_id" in MoveLogModel.__table__.columns
    assert "match_id" in ChatLogModel.__table__.columns
    assert "status" in MatchModel.__table__.columns
