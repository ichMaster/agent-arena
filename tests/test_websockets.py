import pytest
from fastapi.testclient import TestClient
from server.main import app

def test_websocket_without_token():
    client = TestClient(app)
    from starlette.websockets import WebSocketDisconnect
    try:
        with client.websocket_connect("/ws/match/test-match") as websocket:
            pass
    except WebSocketDisconnect as e:
        assert e.code == 1008

def test_websocket_with_token():
    client = TestClient(app)
    response = client.post("/api/v1/lobby/join", json={"match_id": "test-match", "player_name": "p1"})
    token = response.json()["token"]

    with client.websocket_connect(f"/ws/match/test-match?token={token}") as websocket:
        websocket.send_json({"action": "chat", "payload": {"msg": "hello"}})
        data = websocket.receive_json()
        assert data["event_type"] == "chat"
        assert data["data"] == {"msg": "hello"}

def test_concurrent_websockets():
    client = TestClient(app)
    
    response1 = client.post("/api/v1/lobby/join", json={"match_id": "test-match", "player_name": "p1"})
    token1 = response1.json()["token"]
    
    response2 = client.post("/api/v1/lobby/join", json={"match_id": "test-match", "player_name": "p2"})
    token2 = response2.json()["token"]

    with client.websocket_connect(f"/ws/match/test-match?token={token1}") as ws1:
        with client.websocket_connect(f"/ws/match/test-match?token={token2}") as ws2:
            ws1.send_json({"action": "chat", "payload": {"msg": "hi from p1"}})
            
            data1 = ws1.receive_json()
            assert data1["event_type"] == "chat"
            assert data1["data"] == {"msg": "hi from p1"}
            
            data2 = ws2.receive_json()
            assert data2["event_type"] == "chat"
            assert data2["data"] == {"msg": "hi from p1"}
