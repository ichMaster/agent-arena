"""Served app.js tests (ARENA-OPUS-OPUS-027). Assert entry points + wiring at the served-asset level
(no DOM/browser), consistent with the no-build UI. No LLM, no paid call.
"""

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


def test_exposes_entry_points(app_js: str) -> None:
    for fn in ("hostMatch", "joinMatch", "spectateMatch", "routeEvent", "setMatchIdDisplay"):
        assert fn in app_js
    assert "window.arena" in app_js


def test_references_real_endpoints_and_event_names(app_js: str) -> None:
    assert "/api/v1/lobby/match" in app_js
    assert "/api/v1/lobby/join" in app_js
    assert "/ws/match/" in app_js
    for event in ("joined", "state_update", "chat_message", "game_over", "error"):
        assert f"'{event}'" in app_js  # a routeEvent case per server event


def test_match_id_is_never_truncated(app_js: str) -> None:
    # The full id is copied into `agent/agent.py --match-id`; truncation would 404. Guard against it.
    display_idx = app_js.index("function setMatchIdDisplay")
    body = app_js[display_idx:display_idx + 300]
    assert ".slice(" not in body and ".substring(" not in body and ".substr(" not in body


def test_game_over_clears_active_and_new_connection_resets_it(app_js: str) -> None:
    assert "isGameActive = false" in app_js  # on game_over
    assert "isGameActive = true" in app_js   # reset on every new connection (§7)


def test_one_socket_and_open_guarded_send(app_js: str) -> None:
    assert "new WebSocket(" in app_js
    assert "readyState !== WebSocket.OPEN" in app_js  # sends guarded on OPEN
