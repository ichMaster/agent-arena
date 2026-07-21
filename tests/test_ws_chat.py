"""Chat action -> chat_message broadcast (ARENA-OPUS-OPUS-014). Two real WS connections, throwaway
DB; no LLM, no paid call.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from server.database import create_engine, create_session_maker
from server.main import create_app
from server.models import ChatMessage


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/chat.db")
    app = create_app(db_engine=engine, session_maker=create_session_maker(engine))
    with TestClient(app) as c:
        yield c


def _join(client: TestClient, match_id: str, name: str) -> str:
    return str(
        client.post("/api/v1/lobby/join", json={"match_id": match_id, "player_name": name}).json()[
            "token"
        ]
    )


def test_chat_is_broadcast_to_all(client: TestClient) -> None:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    ta, tb = _join(client, match_id, "Alice"), _join(client, match_id, "Bob")
    with client.websocket_connect(f"/ws/match/{match_id}?token={ta}") as wa:
        wa.receive_json()  # joined X
        with client.websocket_connect(f"/ws/match/{match_id}?token={tb}") as wb:
            wb.receive_json()  # joined O
            wa.send_json({"action": "chat", "payload": {"message": "hello there"}})
            msg_a = wa.receive_json()
            msg_b = wb.receive_json()
    for msg in (msg_a, msg_b):
        assert msg == {"event": "chat_message", "payload": {"sender": "X", "message": "hello there"}}


async def test_observer_chat_is_refused(client: TestClient, tmp_path: Path) -> None:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    body = {"match_id": match_id, "player_name": "Watcher", "spectator": True}
    token = client.post("/api/v1/lobby/join", json=body).json()["token"]
    with client.websocket_connect(f"/ws/match/{match_id}?token={token}") as ws:
        ws.receive_json()  # joined (symbol null)
        ws.send_json({"action": "chat", "payload": {"message": "let me in"}})
        assert ws.receive_json() == {"event": "error", "payload": {"detail": "observers cannot chat"}}

    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/chat.db")
    maker = create_session_maker(engine)
    async with maker() as session:
        rows = (await session.execute(select(ChatMessage))).scalars().all()
    assert list(rows) == []  # nothing logged
    await engine.dispose()


async def test_chat_is_persisted(client: TestClient, tmp_path: Path) -> None:
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    token = _join(client, match_id, "Alice")
    with client.websocket_connect(f"/ws/match/{match_id}?token={token}") as ws:
        ws.receive_json()
        ws.send_json({"action": "chat", "payload": {"message": "persisted?"}})
        ws.receive_json()

    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/chat.db")
    maker = create_session_maker(engine)
    async with maker() as session:
        rows = (await session.execute(select(ChatMessage))).scalars().all()
    assert [(r.sender, r.message) for r in rows] == [("X", "persisted?")]
    await engine.dispose()
