"""Served-asset tests for the chat panel (ARENA-OPUS-OPUS-030). No LLM, no paid call."""

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


def test_chat_submit_sends_action_not_optimistic(app_js: str) -> None:
    assert "function handleChatSubmit" in app_js
    idx = app_js.index("function handleChatSubmit")
    body = app_js[idx:idx + 500]
    assert "sendAction('chat'" in body
    assert "input.value = ''" in body
    assert "renderChat" not in body  # never rendered optimistically -- the server echoes it back


def test_render_chat_self_detection_uses_symbol_not_name(app_js: str) -> None:
    assert "function renderChat" in app_js
    idx = app_js.index("function renderChat")
    body = app_js[idx:idx + 700]
    assert "sender === mySymbol" in body
    assert "textContent" in body      # escaped, never innerHTML for untrusted chat
    assert "innerHTML" not in body


def test_error_and_game_over_route_to_system_lines(app_js: str) -> None:
    err = app_js.index("case 'error'")
    assert "renderSystem" in app_js[err:err + 200]
    go = app_js.index("case 'game_over'")
    assert "renderSystem" in app_js[go:go + 300]


def test_chat_form_wired(app_js: str) -> None:
    assert "function wireChat" in app_js
    wui = app_js.index("function wireUI")
    assert "wireChat()" in app_js[wui:wui + 700]
