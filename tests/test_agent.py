import pytest
import asyncio
import uuid
import json
import websockets
from fastapi.testclient import TestClient
from server.main import app
from server.database import async_session_maker
from server.repository import ArenaRepository
from client.agent import run_agent

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
    
    # Run the agent in a background task
    agent_task = asyncio.create_task(run_agent(match_id, server_url, "Agent_X"))
    
    # Wait for the agent to connect and trigger state update
    await asyncio.sleep(0.5)
    
    # Assert background task isn't failed
    assert not agent_task.done() or agent_task.exception() is None
    
    # Cancel the agent task gracefully
    agent_task.cancel()
    try:
        await agent_task
    except asyncio.CancelledError:
        pass
