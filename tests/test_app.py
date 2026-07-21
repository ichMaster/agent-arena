"""App-gate tests (ARENA-OPUS-OPUS-008): health + lifespan-driven schema init. Throwaway DB, no LLM."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from server.database import create_engine, create_session_maker
from server.main import create_app
from server.schemas import JoinRequest


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/app.db")
    app = create_app(db_engine=engine, session_maker=create_session_maker(engine))
    with TestClient(app) as c:  # entering the context runs lifespan -> init_models
        yield c


def test_health(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_lifespan_creates_the_schema(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/app.db")
    app = create_app(db_engine=engine, session_maker=create_session_maker(engine))
    with TestClient(app):
        pass  # lifespan ran init_models on enter
    async with engine.connect() as conn:
        names = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert {"matches", "participants", "moves", "chat_messages"} <= names
    await engine.dispose()


def test_join_request_defaults_spectator_false() -> None:
    req = JoinRequest(match_id="m1", player_name="Alice")
    assert req.spectator is False
