import pytest
import uuid
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
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

def test_websocket_auth_rejection():
    # Test without token
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/match/test_match"):
            pass
    assert exc_info.value.code == 1008

    # Test with invalid token
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/match/test_match?token=invalid_token"):
            pass
    assert exc_info.value.code == 1008

def test_websocket_auth_success():
    valid_token = str(uuid.uuid4())
    with client.websocket_connect(f"/ws/match/test_match?token={valid_token}") as websocket:
        assert True

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
