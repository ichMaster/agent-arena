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


def test_ui_board_cells_start_disabled() -> None:
    response = client.get("/ui/")
    assert response.status_code == 200
    assert 'class="cell disabled" id="cell-0"' in response.text
