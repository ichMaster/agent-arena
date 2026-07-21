"""Agent-vs-agent end-to-end over the real server (ARENA-OPUS-OPUS-036, roadmap §v05.02).

Two real AgentSessions (Ironclaw vs Bastion, both LLMs scripted-mocked) play a full game to game_over
over real WS connections. The v04 headline scenario as an automated test. Zero paid calls.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from agent.agent import AgentSession
from agent.memory import MemoryWindow
from agent.profile import AgentProfile
from agent.schemas import AgentResponse
from server.database import create_engine, create_session_maker
from server.main import create_app


@pytest.fixture
def lobby(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/ava.db")
    app = create_app(db_engine=engine, session_maker=create_session_maker(engine))
    with TestClient(app) as client:
        yield client


def _join(client: TestClient, match_id: str, name: str) -> str:
    return str(
        client.post("/api/v1/lobby/join", json={"match_id": match_id, "player_name": name}).json()[
            "token"
        ]
    )


def _mock_llm(*replies: AgentResponse) -> AsyncMock:
    llm = AsyncMock()
    llm.generate_structured_response = AsyncMock(side_effect=list(replies))
    return llm


async def _feed_both(
    ws_x: Any, ws_o: Any, sx: AgentSession, so: AgentSession, event: dict[str, Any]
) -> None:
    """Deliver one broadcast to both sessions; each acts only on its own turn (on_event is a no-op
    unless current_turn matches its symbol)."""
    for action in await sx.on_event(event):
        ws_x.send_json(action)
    for action in await so.on_event(event):
        ws_o.send_json(action)


async def test_agent_vs_agent_plays_to_game_over(lobby: TestClient) -> None:
    match_id = lobby.post("/api/v1/lobby/match").json()["match_id"]
    profile_x = AgentProfile.load_from_yaml("profiles/aggressive.yml")  # Ironclaw
    profile_o = AgentProfile.load_from_yaml("profiles/cautious.yml")  # Bastion
    token_x = _join(lobby, match_id, profile_x.name)
    token_o = _join(lobby, match_id, profile_o.name)

    llm_x = _mock_llm(
        AgentResponse(move=0, comment="center of the storm"),
        AgentResponse(move=1, comment="pressing on"),
        AgentResponse(move=2, comment="top row, all mine"),
    )
    llm_o = _mock_llm(
        AgentResponse(move=3, comment="holding the line"),
        AgentResponse(move=4, comment="steady as she goes"),
    )
    mem_x = MemoryWindow(profile_x.memory_limit)
    mem_o = MemoryWindow(profile_o.memory_limit)
    sx = AgentSession(profile_x, llm_x, mem_x)
    so = AgentSession(profile_o, llm_o, mem_o)

    with lobby.websocket_connect(f"/ws/match/{match_id}?token={token_x}") as wx, \
         lobby.websocket_connect(f"/ws/match/{match_id}?token={token_o}") as wo:
        ev_x = wx.receive_json()
        ev_o = wo.receive_json()
        assert ev_x["payload"]["symbol"] == "X" and ev_o["payload"]["symbol"] == "O"

        # X moves first, triggered by its own joined event.
        for action in await sx.on_event(ev_x):
            wx.send_json(action)
        assert await so.on_event(ev_o) == []  # not O's turn yet

        result_event: dict[str, Any] | None = None
        for _ in range(20):  # generous bound; the real driver is the game_over break
            e_x = wx.receive_json()
            e_o = wo.receive_json()
            assert e_x == e_o  # the same broadcast reaches both sockets
            await _feed_both(wx, wo, sx, so, e_x)
            if e_x["event"] == "game_over":
                result_event = e_x
                break

    assert result_event == {"event": "game_over", "payload": {"result": "X"}}
    assert sx.finished and so.finished
    # Exact call counts: no action on the terminal state_update (current_turn null).
    assert llm_x.generate_structured_response.await_count == 3
    assert llm_o.generate_structured_response.await_count == 2
    # Opponent moves recorded in each side's memory (never its own).
    ev_x_mem = mem_x.events()
    assert "O played 3" in ev_x_mem and "O played 4" in ev_x_mem
    assert not any("X played" in e for e in ev_x_mem)
    ev_o_mem = mem_o.events()
    assert "X played 0" in ev_o_mem and "X played 2" in ev_o_mem
    assert not any("O played" in e for e in ev_o_mem)
