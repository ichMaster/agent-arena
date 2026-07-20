"""Served-asset tests for the chat wiring (ARENA-OPUS-030). No LLM, no paid call."""

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


def test_chat_render_functions_defined(app_js: str) -> None:
    assert "function renderChat" in app_js
    assert "function renderSystem" in app_js


def test_chat_form_sends_chat_action(app_js: str) -> None:
    assert "function submitChat" in app_js
    assert "sendAction('chat'" in app_js
    assert "value.trim()" in app_js  # trimmed, non-empty guard


def test_self_detection_uses_symbol_not_name(app_js: str) -> None:
    # Reconciliation: chat_message.sender is the seat symbol, so self = sender === mySymbol.
    rc = app_js.index("function renderChat")
    body = app_js[rc:rc + 500]
    assert "sender === mySymbol" in body
    assert "textContent" in body  # untrusted content escaped, never innerHTML
    assert "innerHTML" not in body


def test_chat_message_and_error_routed(app_js: str) -> None:
    chat_idx = app_js.index("case 'chat_message'")
    assert "renderChat(" in app_js[chat_idx:chat_idx + 120]
    err_idx = app_js.index("case 'error'")
    assert "renderSystem(" in app_js[err_idx:err_idx + 120]  # v03.01 review #2 closed
