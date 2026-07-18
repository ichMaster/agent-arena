from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)


def test_ui_index_is_served() -> None:
    response = client.get("/ui/")
    assert response.status_code == 200
    assert "Agent Arena" in response.text
    assert "<script" not in response.text  # v04.01: no JS yet


def test_ui_stylesheet_is_served() -> None:
    response = client.get("/ui/styles.css")
    assert response.status_code == 200
    assert "glass-panel" in response.text
