from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)


def test_ui_index_is_served() -> None:
    response = client.get("/ui/")
    assert response.status_code == 200
    assert "Agent Arena" in response.text
    assert '<script src="app.js">' in response.text


def test_ui_stylesheet_is_served() -> None:
    response = client.get("/ui/styles.css")
    assert response.status_code == 200
    assert "glass-panel" in response.text


def test_ui_app_js_is_served() -> None:
    response = client.get("/ui/app.js")
    assert response.status_code == 200
    assert "hostMatch" in response.text
    assert "joinExistingMatch" in response.text
    assert "connectSocket" in response.text
    assert "routeEvent" in response.text
    assert "renderBoard" in response.text
    assert "handleCellClick" in response.text
    assert "renderChat" in response.text
    assert "handleGameOver" in response.text


def test_ui_board_cells_start_disabled() -> None:
    response = client.get("/ui/")
    assert response.status_code == 200
    assert 'class="cell disabled" id="cell-0"' in response.text


def test_ui_app_js_displays_the_full_match_id_not_a_truncated_prefix() -> None:
    """Regression: the display used to show only matchId.slice(0, 8) — cosmetic,
    but it's also the exact string the README tells users to copy into
    `client/agent.py --match-id ...` / the swarm script, so a truncated id
    silently 404s against the real match (see server/main.py's join validation)."""
    response = client.get("/ui/app.js")
    assert response.status_code == 200
    assert ".slice(0, 8)" not in response.text
    assert "setMatchIdDisplay" in response.text


def test_ui_assets_are_never_cached_by_the_browser() -> None:
    """StaticFiles alone sets ETag/Last-Modified but no Cache-Control, which
    lets browsers heuristically cache /ui/* and keep serving a stale
    index.html/app.js/styles.css after an edit — confusing during active
    development, since a genuinely-fixed bug can appear to still reproduce."""
    for path in ("/ui/", "/ui/app.js", "/ui/styles.css"):
        response = client.get(path)
        assert response.headers.get("cache-control") == "no-store", path


def test_non_ui_routes_are_unaffected_by_the_no_store_header() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers.get("cache-control") != "no-store"


def test_ui_has_a_real_spectate_action_distinct_from_join() -> None:
    """Regression: the only way to open an existing match in the browser was
    "Join Match", which claims a real player seat server-side. A real swarm
    run broke because a spectating browser session did exactly that,
    starving one of the two scripted agents of a seat. There must be a
    genuinely separate spectate action that never claims one."""
    html = client.get("/ui/").text
    assert 'id="spectate-match-btn"' in html

    js = client.get("/ui/app.js").text
    assert "spectateMatch" in js
    assert "spectator: isSpectator" in js  # the POST /lobby/join body actually carries the flag


def test_ui_join_and_host_still_default_to_non_spectator() -> None:
    js = client.get("/ui/app.js").text
    assert "promptAndJoin(false)" in js
