"""Integration tests for the FastAPI app gate (architecture §3, §6.1) via ``TestClient``.

Each test binds the app to a throwaway temp-file DB, so entering the client runs ``init_models``
against that DB — the dev ``./arena.db`` is never touched. No LLM, no paid call.
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.database import create_engine, create_session_maker
from server.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/app.db")
    maker = create_session_maker(engine)
    app = create_app(db_engine=engine, session_maker=maker)
    with TestClient(app) as test_client:  # entering runs the lifespan (init_models)
        yield test_client


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_lifespan_runs_init_models(tmp_path: Path) -> None:
    db_path = tmp_path / "startup.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    maker = create_session_maker(engine)
    app = create_app(db_engine=engine, session_maker=maker)
    with TestClient(app):  # startup runs init_models against the throwaway DB
        pass
    connection = sqlite3.connect(db_path)
    try:
        names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        connection.close()
    assert {"matches", "participants", "moves", "chat_messages"} <= names
