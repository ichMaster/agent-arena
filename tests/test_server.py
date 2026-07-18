from fastapi.testclient import TestClient
from server.main import app
import uuid

client = TestClient(app)

def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_create_match():
    response = client.post("/api/v1/lobby/match")
    assert response.status_code == 200
    data = response.json()
    assert "match_id" in data
    # verify it's a valid uuid
    uuid_obj = uuid.UUID(data["match_id"], version=4)
    assert str(uuid_obj) == data["match_id"]

def test_join_match():
    payload = {"match_id": "test-match", "player_name": "Alice"}
    response = client.post("/api/v1/lobby/join", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert isinstance(data["token"], str)

def test_join_match_invalid():
    response = client.post("/api/v1/lobby/join", json={"player_name": "Alice"})
    assert response.status_code == 422
