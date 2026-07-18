import uuid
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from server.main import app
from server.database import Base, engine, async_session_maker
from server.repository import ArenaRepository

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

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

@pytest.mark.asyncio
async def test_websocket_chat_persistence_and_broadcast():
    # First create a match
    resp_match = client.post("/api/v1/lobby/match")
    match_id = resp_match.json()["match_id"]
    
    # Manually persist the match in the DB to satisfy foreign keys
    async with async_session_maker() as session:
        repo = ArenaRepository(session)
        from server.models import MatchModel, MatchStatus
        match = MatchModel(id=match_id, status=MatchStatus.PENDING)
        session.add(match)
        await session.commit()
    
    # Generate token
    token = str(uuid.uuid4())
    
    # Connect
    with client.websocket_connect(f"/ws/match/{match_id}?token={token}") as websocket:
        # Send a chat message action
        action_payload = {
            "action": "chat_message",
            "payload": {
                "sender": "Alice",
                "message": "Hi everyone!"
            }
        }
        websocket.send_json(action_payload)
        
        # Receive the broadcasted ServerPushEvent event back
        response = websocket.receive_json()
        assert response["event"] == "chat_message"
        assert response["data"]["sender"] == "Alice"
        assert response["data"]["message"] == "Hi everyone!"
        
    # Verify persistence in the DB
    async with async_session_maker() as session:
        repo = ArenaRepository(session)
        chats = await repo.get_chats(match_id)
        assert len(chats) == 1
        assert chats[0].sender == "Alice"
        assert chats[0].message == "Hi everyone!"
