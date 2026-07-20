"""Integration tests for the served arena shell (ARENA-OPUS-026). Served-asset level; no LLM."""

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


def test_index_has_all_targeted_elements(client: TestClient) -> None:
    html = client.get("/ui/").text
    # lobby controls
    for el in ('id="btn-host"', 'id="btn-join"', 'id="btn-observe"'):
        assert el in html
    # status + the FULL match id element
    assert 'id="status-label"' in html and 'id="match-id"' in html
    # board with nine real <button> cells
    assert 'id="board"' in html
    for i in range(9):
        assert f'id="cell-{i}"' in html
    assert html.count("<button") >= 9  # cells are buttons (a11y §9)
    # turn banner + two player cards
    assert 'id="turn-banner"' in html and 'id="card-x"' in html and 'id="card-o"' in html
    # chat count / messages / form / input
    for el in ('id="chat-count"', 'id="messages"', 'id="chat-form"', 'id="chat-input"'):
        assert el in html
    # links its own assets, no CDN
    assert 'href="styles.css"' in html and 'src="app.js"' in html
    assert "http://" not in html and "https://" not in html  # self-contained


def test_styles_served_with_tokens(client: TestClient) -> None:
    resp = client.get("/ui/styles.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]
    css = resp.text
    assert "--x: #55a0ff" in css and "--o: #ff5aa0" in css  # X/O tokens
    assert "@media (max-width: 860px)" in css  # responsive collapse
    assert "prefers-reduced-motion" in css  # a11y motion guard
