"""Served-asset tests for the board read path (ARENA-OPUS-OPUS-028). No LLM, no paid call."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.database import create_engine, create_session_maker
from server.main import create_app


@pytest.fixture
def app_js(tmp_path: Path) -> str:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/ui.db")
    app = create_app(db_engine=engine, session_maker=create_session_maker(engine))
    with TestClient(app) as c:
        return c.get("/ui/app.js").text


def test_defines_renderers(app_js: str) -> None:
    assert "function renderBoard" in app_js
    assert "function renderPlayers" in app_js
    assert "function renderTurnBanner" in app_js


def test_interactivity_gated_on_my_turn_and_active(app_js: str) -> None:
    idx = app_js.index("function renderBoard")
    body = app_js[idx:idx + 900]
    assert "isGameActive" in body
    assert "currentTurn === mySymbol" in body
    assert "cell.disabled = !playable" in body  # real disabled attribute, not just a class


def test_joined_and_state_update_call_the_renderers(app_js: str) -> None:
    joined_idx = app_js.index("case 'joined'")
    assert "renderBoard(" in app_js[joined_idx:joined_idx + 500]
    su_idx = app_js.index("case 'state_update'")
    assert "renderBoard(" in app_js[su_idx:su_idx + 300]


def test_active_card_follows_current_turn(app_js: str) -> None:
    idx = app_js.index("function renderPlayers")
    body = app_js[idx:idx + 700]
    assert "currentTurn === sym" in body  # only the current-turn card is .active
