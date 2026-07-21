"""Static mount + no-store middleware tests (ARENA-OPUS-OPUS-025). Throwaway DB, no LLM."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.database import create_engine, create_session_maker
from server.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/ui.db")
    app = create_app(db_engine=engine, session_maker=create_session_maker(engine))
    with TestClient(app) as c:
        yield c


def test_ui_root_serves_html_with_no_store(client: TestClient) -> None:
    resp = client.get("/ui/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert resp.headers.get("cache-control") == "no-store"


def test_ui_asset_carries_no_store(client: TestClient) -> None:
    # index.html is the served asset at this phase; the header still applies.
    resp = client.get("/ui/index.html")
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == "no-store"


def test_non_ui_route_lacks_no_store(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") != "no-store"
