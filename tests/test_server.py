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


def test_join_match_returns_token() -> None:
    response = client.post(
        "/api/v1/lobby/join", json={"match_id": str(uuid.uuid4()), "player_name": "Ada"}
    )
    assert response.status_code == 200
    assert "token" in response.json()


def test_join_match_rejects_missing_fields() -> None:
    response = client.post("/api/v1/lobby/join", json={"match_id": str(uuid.uuid4())})
    assert response.status_code == 422
