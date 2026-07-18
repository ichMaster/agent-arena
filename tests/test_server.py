import uuid
import pytest
import pytest_asyncio
import threading
import time
import socket
import json
import uvicorn
import websockets
from fastapi.testclient import TestClient
from server.main import app
from server.database import Base, engine, async_session_maker
from server.repository import ArenaRepository

client = TestClient(app)

def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_serve_static_ui():
    # Verify index.html is served at root
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Agent Arena" in response.text
    
    # Verify styles.css is served
    response_css = client.get("/static/styles.css")
    assert response_css.status_code == 200
    assert "text/css" in response_css.headers["content-type"]


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
        init_state = websocket.receive_json()
        assert init_state["event"] == "state_update"
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

@pytest.mark.asyncio
async def test_websocket_concurrent_clients(server_port):
    # First create a match and save to database
    resp_match = client.post("/api/v1/lobby/match")
    match_id = resp_match.json()["match_id"]
    
    async with async_session_maker() as session:
        repo = ArenaRepository(session)
        from server.models import MatchModel, MatchStatus
        match = MatchModel(id=match_id, status=MatchStatus.PENDING)
        session.add(match)
        await session.commit()
        
    # Generate distinct tokens
    token1 = str(uuid.uuid4())
    token2 = str(uuid.uuid4())
    
    # Connect client 1 and client 2 concurrently using real async websockets
    url1 = f"ws://127.0.0.1:{server_port}/ws/match/{match_id}?token={token1}"
    url2 = f"ws://127.0.0.1:{server_port}/ws/match/{match_id}?token={token2}"
    
    async with websockets.connect(url1) as ws1:
        init_state1 = json.loads(await ws1.recv())
        assert init_state1["event"] == "state_update"
        
        async with websockets.connect(url2) as ws2:
            init_state2 = json.loads(await ws2.recv())
            assert init_state2["event"] == "state_update"
            
            # Client 1 sends a message
            action1 = {
                "action": "chat_message",
                "payload": {"sender": "Client 1", "message": "Hello from 1"}
            }
            await ws1.send(json.dumps(action1))
            
            # Both should receive Client 1's message
            res1 = json.loads(await ws1.recv())
            res2 = json.loads(await ws2.recv())
            
            assert res1["event"] == "chat_message"
            assert res1["data"]["sender"] == "Client 1"
            assert res1["data"]["message"] == "Hello from 1"
            
            assert res2["event"] == "chat_message"
            assert res2["data"]["sender"] == "Client 1"
            assert res2["data"]["message"] == "Hello from 1"
            
            # Client 2 sends a message
            action2 = {
                "action": "chat_message",
                "payload": {"sender": "Client 2", "message": "Hello from 2"}
            }
            await ws2.send(json.dumps(action2))
            
            # Both should receive Client 2's message
            res1_new = json.loads(await ws1.recv())
            res2_new = json.loads(await ws2.recv())
            
            assert res1_new["event"] == "chat_message"
            assert res1_new["data"]["sender"] == "Client 2"
            assert res1_new["data"]["message"] == "Hello from 2"
            
            assert res2_new["event"] == "chat_message"
            assert res2_new["data"]["sender"] == "Client 2"
            assert res2_new["data"]["message"] == "Hello from 2"

@pytest.mark.asyncio
async def test_websocket_match_lifecycle(server_port):
    # Create match and persist to DB
    resp_match = client.post("/api/v1/lobby/match")
    match_id = resp_match.json()["match_id"]
    
    async with async_session_maker() as session:
        repo = ArenaRepository(session)
        from server.models import MatchModel, MatchStatus
        match = MatchModel(id=match_id, status=MatchStatus.PENDING)
        session.add(match)
        await session.commit()
        
    token1 = str(uuid.uuid4())
    token2 = str(uuid.uuid4())
    
    url1 = f"ws://127.0.0.1:{server_port}/ws/match/{match_id}?token={token1}"
    url2 = f"ws://127.0.0.1:{server_port}/ws/match/{match_id}?token={token2}"
    
    async with websockets.connect(url1) as ws1:
        # P1 receives initial state on connection
        init_state1 = json.loads(await ws1.recv())
        assert init_state1["event"] == "state_update"
        assert init_state1["data"]["board"] == [None] * 9
        
        async with websockets.connect(url2) as ws2:
            # P2 receives initial state on connection
            init_state2 = json.loads(await ws2.recv())
            assert init_state2["event"] == "state_update"
            assert init_state2["data"]["board"] == [None] * 9
            
            # P1 sends invalid move (out of bounds)
            await ws1.send(json.dumps({"action": "submit_move", "payload": {"move": 9}}))
            err_p1 = json.loads(await ws1.recv())
            assert "error" in err_p1
            
            # P1 sends valid move (0)
            await ws1.send(json.dumps({"action": "submit_move", "payload": {"move": 0}}))
            
            # Both should receive state update (cell 0 is X)
            state_p1 = json.loads(await ws1.recv())
            state_p2 = json.loads(await ws2.recv())
            assert state_p1["event"] == "state_update"
            assert state_p1["data"]["board"][0] == "X"
            assert state_p2["event"] == "state_update"
            assert state_p2["data"]["board"][0] == "X"
            
            # P2 sends valid move (1)
            await ws2.send(json.dumps({"action": "submit_move", "payload": {"move": 1}}))
            state_p1 = json.loads(await ws1.recv())
            state_p2 = json.loads(await ws2.recv())
            assert state_p1["data"]["board"][1] == "O"
            
            # P1 sends move (4)
            await ws1.send(json.dumps({"action": "submit_move", "payload": {"move": 4}}))
            await ws1.recv()
            await ws2.recv()
            
            # P2 sends move (3)
            await ws2.send(json.dumps({"action": "submit_move", "payload": {"move": 3}}))
            await ws1.recv()
            await ws2.recv()
            
            # P1 sends winning move (8)
            await ws1.send(json.dumps({"action": "submit_move", "payload": {"move": 8}}))
            
            # Both receive final state update
            state_p1 = json.loads(await ws1.recv())
            state_p2 = json.loads(await ws2.recv())
            assert state_p1["data"]["board"][8] == "X"
            
            # Both receive game_over event
            go_p1 = json.loads(await ws1.recv())
            go_p2 = json.loads(await ws2.recv())
            assert go_p1["event"] == "game_over"
            assert go_p1["data"]["winner"] == "X"
            assert go_p2["event"] == "game_over"
            assert go_p2["data"]["winner"] == "X"
            
            # Connection closes automatically
            try:
                await ws1.recv()
                assert False, "Connection ws1 should have been closed"
            except websockets.exceptions.ConnectionClosed:
                pass
                
            try:
                await ws2.recv()
                assert False, "Connection ws2 should have been closed"
            except websockets.exceptions.ConnectionClosed:
                pass
