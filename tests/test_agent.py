import pytest
import asyncio
import uuid
import json
import websockets
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from server.main import app
from server.database import async_session_maker
from server.repository import ArenaRepository
from client.agent import run_agent, AgentResponse

client = TestClient(app)

@pytest.mark.asyncio
async def test_agent_run_lifecycle(server_port):
    # Create match and persist to DB
    resp_match = client.post("/api/v1/lobby/match")
    match_id = resp_match.json()["match_id"]
    
    async with async_session_maker() as session:
        repo = ArenaRepository(session)
        from server.models import MatchModel, MatchStatus
        match = MatchModel(id=match_id, status=MatchStatus.PENDING)
        session.add(match)
        await session.commit()
        
    server_url = f"http://127.0.0.1:{server_port}"
    
    # Mock GeminiClient with a delayed response to allow spectator connection first
    mock_gemini = AsyncMock()
    async def delayed_generate(prompt, schema):
        await asyncio.sleep(0.4)
        return AgentResponse(move=4, comment="I am superior.")
    mock_gemini.generate_structured_response.side_effect = delayed_generate
    
    with patch("client.agent.GeminiClient", return_value=mock_gemini):
        # Run the agent task (will be X)
        agent_task = asyncio.create_task(run_agent(match_id, server_url, "Agent_X", "X"))
        
        # Wait a tiny bit for the agent to establish connection
        await asyncio.sleep(0.1)
        
        # Connect the spectator (will be O)
        token_spectator = str(uuid.uuid4())
        ws_spectator_url = f"ws://127.0.0.1:{server_port}/ws/match/{match_id}?token={token_spectator}"
        
        async with websockets.connect(ws_spectator_url) as ws_spec:
            # Spectator receives initial empty state
            init_state = json.loads(await ws_spec.recv())
            assert init_state["event"] == "state_update"
            assert init_state["data"]["board"][4] is None
            
            # Now wait for the agent to finish sleeping and send actions
            chat_evt = json.loads(await ws_spec.recv())
            assert chat_evt["event"] == "chat_message"
            assert chat_evt["data"]["sender"] == "Agent_X"
            assert chat_evt["data"]["message"] == "I am superior."
            
            # Spectator receives state update showing move applied
            state_evt = json.loads(await ws_spec.recv())
            assert state_evt["event"] == "state_update"
            assert state_evt["data"]["board"][4] == "X"
            
            # Assert background task is healthy
            assert not agent_task.done() or agent_task.exception() is None
            
            # Cancel task gracefully
            agent_task.cancel()
            try:
                await agent_task
            except asyncio.CancelledError:
                pass
