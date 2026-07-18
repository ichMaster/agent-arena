import pytest
from unittest.mock import AsyncMock
from server.websockets import ConnectionManager, ServerPushEvent

@pytest.mark.asyncio
async def test_connection_manager_tracking():
    manager = ConnectionManager()
    
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    match_id = "test-match"
    
    # Test connect
    await manager.connect(ws1, match_id)
    assert match_id in manager.matches
    assert len(manager.matches[match_id].players) == 1
    assert manager.matches[match_id].players[0] is ws1
    assert ws1.accept.called
    
    # Test connect second client
    await manager.connect(ws2, match_id)
    assert len(manager.matches[match_id].players) == 2
    assert manager.matches[match_id].players[1] is ws2
    
    # Test broadcast
    event = ServerPushEvent(event="chat_message", data={"sender": "User", "message": "Hi"})
    await manager.broadcast(match_id, event)
    assert ws1.send_json.called
    assert ws2.send_json.called
    
    # Test disconnect
    manager.disconnect(ws1, match_id)
    assert len(manager.matches[match_id].players) == 1
    assert manager.matches[match_id].players[0] is ws2
    
    # Test disconnect last client clears match key
    manager.disconnect(ws2, match_id)
    assert match_id not in manager.matches
