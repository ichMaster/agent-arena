import uuid

from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_match_returns_valid_uuid() -> None:
    response = client.post("/api/v1/lobby/match")
    assert response.status_code == 200
    body = response.json()
    assert "match_id" in body
    assert uuid.UUID(body["match_id"]).version == 4
