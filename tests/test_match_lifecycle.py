import pytest
from fastapi.testclient import TestClient
from server.main import app

def test_match_lifecycle():
    client = TestClient(app)
    
    res1 = client.post("/api/v1/lobby/join", json={"match_id": "game1", "player_name": "p1"})
    token1 = res1.json()["token"]
    res2 = client.post("/api/v1/lobby/join", json={"match_id": "game1", "player_name": "p2"})
    token2 = res2.json()["token"]
    
    with client.websocket_connect(f"/ws/match/game1?token={token1}") as ws1:
        with client.websocket_connect(f"/ws/match/game1?token={token2}") as ws2:
            data1 = ws1.receive_json()
            assert data1["event_type"] == "connected"
            assert data1["data"]["symbol"] == "X"
            
            data2 = ws2.receive_json()
            assert data2["event_type"] == "connected"
            assert data2["data"]["symbol"] == "O"
            
            ws2.send_json({"action": "submit_move", "payload": {"move": 0}})
            err_data = ws2.receive_json()
            assert err_data["event_type"] == "error"
            assert err_data["data"]["message"] == "invalid move"
            
            ws1.send_json({"action": "submit_move", "payload": {"move": 0}})
            su1_1 = ws1.receive_json()
            su1_2 = ws2.receive_json()
            assert su1_1["event_type"] == "state_update"
            assert su1_2["event_type"] == "state_update"
            assert su1_1["data"]["board"][0] == "X"
            
            ws2.send_json({"action": "submit_move", "payload": {"move": 3}})
            ws1.receive_json()
            ws2.receive_json()
            
            ws1.send_json({"action": "submit_move", "payload": {"move": 1}})
            ws1.receive_json()
            ws2.receive_json()
            
            ws2.send_json({"action": "submit_move", "payload": {"move": 4}})
            ws1.receive_json()
            ws2.receive_json()
            
            ws1.send_json({"action": "submit_move", "payload": {"move": 2}})
            
            su3_1 = ws1.receive_json()
            su3_2 = ws2.receive_json()
            assert su3_1["event_type"] == "state_update"
            
            go1 = ws1.receive_json()
            go2 = ws2.receive_json()
            assert go1["event_type"] == "game_over"
            assert go1["data"]["winner"] == "X"
