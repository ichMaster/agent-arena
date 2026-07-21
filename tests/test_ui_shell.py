"""Served arena-shell tests (ARENA-OPUS-OPUS-026). Assert structure at the served-asset level."""

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


def test_index_has_all_targeted_ids(client: TestClient) -> None:
    html = client.get("/ui/").text
    for needed in (
        'id="board"', 'id="match-id"', 'id="status-label"', 'id="turn-banner"',
        'id="btn-host"', 'id="btn-join"', 'id="btn-observe"',
        'id="card-x"', 'id="card-o"', 'id="chat-count"', 'id="messages"',
        'id="chat-form"', 'id="chat-input"',
    ):
        assert needed in html, f"missing {needed}"
    for i in range(9):
        assert f'id="cell-{i}"' in html
    assert 'href="styles.css"' in html and 'src="app.js"' in html


def test_cells_are_real_buttons(client: TestClient) -> None:
    html = client.get("/ui/").text
    assert '<button class="cell empty" id="cell-0"' in html  # real <button>, a11y


def test_styles_serve_with_tokens(client: TestClient) -> None:
    css = client.get("/ui/styles.css")
    assert css.status_code == 200
    assert "--x: #55a0ff" in css.text and "--o: #ff5aa0" in css.text
    assert "@media (max-width: 860px)" in css.text  # responsive collapse
    assert "prefers-reduced-motion" in css.text


def test_no_external_asset_references(client: TestClient) -> None:
    html = client.get("/ui/").text
    assert "http://" not in html and "https://" not in html  # self-contained, no CDN
