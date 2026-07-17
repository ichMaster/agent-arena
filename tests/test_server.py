from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_create_match():
    response = client.post("/api/v1/lobby/match")
    assert response.status_code == 200
    data = response.json()
    assert "match_id" in data
    assert isinstance(data["match_id"], str)
    assert len(data["match_id"]) > 0

def test_join_match():
    response = client.post("/api/v1/lobby/join", json={
        "match_id": "test-id",
        "player_name": "Test Player"
    })
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert isinstance(data["token"], str)
    assert len(data["token"]) > 0

def test_join_match_missing_fields():
    response = client.post("/api/v1/lobby/join", json={"match_id": "test-id"})
    assert response.status_code == 422
