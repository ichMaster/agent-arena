import uuid
import pytest
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
    match_id = data["match_id"]
    # Verify that the returned match_id is a valid UUID
    try:
        val = uuid.UUID(match_id, version=4)
        assert str(val) == match_id
    except ValueError:
        assert False, f"Returned match_id {match_id} is not a valid UUID4"

def test_join_match():
    # First create a match to get a match_id
    resp_match = client.post("/api/v1/lobby/match")
    match_id = resp_match.json()["match_id"]
    
    # Send a valid join request
    payload = {"match_id": match_id, "player_name": "Player 1"}
    response = client.post("/api/v1/lobby/join", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    token = data["token"]
    # Ensure it returns a non-empty string token
    assert isinstance(token, str)
    assert len(token) > 0

def test_join_match_missing_fields():
    # Send request with missing player_name
    payload = {"match_id": "some-match-id"}
    response = client.post("/api/v1/lobby/join", json=payload)
    assert response.status_code == 422

def test_websocket_auth_handshake():
    match_id = "test-match"
    
    # 1. Connect without token parameter
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/match/{match_id}") as websocket:
            pass

    # 2. Connect with invalid token parameter
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/match/{match_id}?token=invalid-token") as websocket:
            pass

    # 3. Connect with valid UUID token parameter
    valid_token = str(uuid.uuid4())
    with client.websocket_connect(f"/ws/match/{match_id}?token={valid_token}") as websocket:
        # Connection succeeds
        pass
