import uuid
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
