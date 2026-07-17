import pytest
from server.websockets import ConnectionManager, ServerPushEvent

class MockWebSocket:
    def __init__(self):
        self.accepted = False
        self.messages = []
    
    async def accept(self):
        self.accepted = True
        
    async def send_text(self, data: str):
        self.messages.append(data)

@pytest.mark.asyncio
async def test_connection_manager():
    manager = ConnectionManager()
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    
    # Test connect
    await manager.connect(ws1, "match1")
    assert ws1.accepted
    assert len(manager.active_connections["match1"]) == 1
    
    await manager.connect(ws2, "match1")
    assert len(manager.active_connections["match1"]) == 2
    
    # Test broadcast
    event = ServerPushEvent(event="chat", data={"message": "hello"})
    await manager.broadcast("match1", event)
    assert len(ws1.messages) == 1
    assert len(ws2.messages) == 1
    
    # Test disconnect
    manager.disconnect(ws1, "match1")
    assert len(manager.active_connections["match1"]) == 1
    
    manager.disconnect(ws2, "match1")
    assert "match1" not in manager.active_connections
