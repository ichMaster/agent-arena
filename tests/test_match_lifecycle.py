import pytest
import uuid
import json
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
from server.main import app
from server.database import engine, Base
import pytest_asyncio

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

client = TestClient(app)

def test_full_match_lifecycle():
    # 1. Create Match
    match_resp = client.post("/api/v1/lobby/match")
    match_id = match_resp.json()["match_id"]
    
    token1 = str(uuid.uuid4())
    token2 = str(uuid.uuid4())
    token3 = str(uuid.uuid4())
    
    url1 = f"/ws/match/{match_id}?token={token1}"
    url2 = f"/ws/match/{match_id}?token={token2}"
    url3 = f"/ws/match/{match_id}?token={token3}" # Spectator
    
    # We must use separate clients to avoid connection locking in Starlette TestClient if needed.
    # Actually, starlette TestClient handles concurrent websockets if used in context managers sequentially
    # Wait, starlette testclient `websocket_connect` blocks if we just wait on `receive_json`.
    # Let's connect them
    with client.websocket_connect(url1) as ws1, client.websocket_connect(url2) as ws2, client.websocket_connect(url3) as ws3:
        # Upon connect, all should receive initial state
        state1 = ws1.receive_json()
        state2 = ws2.receive_json()
        state3 = ws3.receive_json()
        
        assert state1["event"] == "state_update"
        assert state2["event"] == "state_update"
        assert state1["data"]["current_turn"] == "X"
        
        # ws1 is X, ws2 is O, ws3 is Spectator
        
        # Spectator tries to move (invalid)
        ws3.send_json({
            "action": "submit_move",
            "payload": {"move": 0}
        })
        err3 = ws3.receive_json()
        assert "error" in err3
        assert err3["error"] == "You are not a player in this match."
        
        # O (ws2) tries to move out of turn (invalid)
        ws2.send_json({
            "action": "submit_move",
            "payload": {"move": 1}
        })
        err2 = ws2.receive_json()
        assert "error" in err2
        assert err2["error"] == "Invalid move."
        
        # X (ws1) plays top left (0)
        ws1.send_json({
            "action": "submit_move",
            "payload": {"move": 0}
        })
        # All receive state
        s1 = ws1.receive_json()
        s2 = ws2.receive_json()
        s3 = ws3.receive_json()
        assert s1["event"] == "state_update"
        assert s1["data"]["board"][0] == "X"
        assert s1["data"]["current_turn"] == "O"
        
        # O (ws2) plays middle left (3)
        ws2.send_json({
            "action": "submit_move",
            "payload": {"move": 3}
        })
        ws1.receive_json()
        ws2.receive_json()
        ws3.receive_json()
        
        # X (ws1) plays top middle (1)
        ws1.send_json({
            "action": "submit_move",
            "payload": {"move": 1}
        })
        ws1.receive_json()
        ws2.receive_json()
        ws3.receive_json()
        
        # O (ws2) plays middle center (4)
        ws2.send_json({
            "action": "submit_move",
            "payload": {"move": 4}
        })
        ws1.receive_json()
        ws2.receive_json()
        ws3.receive_json()
        
        # X (ws1) plays top right (2) - WINS!
        ws1.send_json({
            "action": "submit_move",
            "payload": {"move": 2}
        })
        
        # Receive final state
        s1 = ws1.receive_json()
        s2 = ws2.receive_json()
        s3 = ws3.receive_json()
        
        assert s1["event"] == "state_update"
        assert s1["data"]["status"] == "X"
        
        # Receive game over
        go1 = ws1.receive_json()
        go2 = ws2.receive_json()
        go3 = ws3.receive_json()
        
        assert go1["event"] == "game_over"
        assert go1["data"]["winner"] == "X"
        
        # Server should close connections gracefully
        with pytest.raises(WebSocketDisconnect) as exc1:
            ws1.receive_json()
        assert exc1.value.code == 1000
