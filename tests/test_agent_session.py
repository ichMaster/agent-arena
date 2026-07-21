"""AgentSession event-core + full-game integration (ARENA-OPUS-OPUS-024, v02 gate).

The LLM is a scripted mock (incl. one illegal reply -> retry) -- zero paid calls. Events flow through
a real TestClient WebSocket against the real app + throwaway DB; a scripted opponent (plain WS sends,
no LLM) holds the second seat.
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
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/agent.db")
    app = create_app(db_engine=engine, session_maker=create_session_maker(engine))
    with TestClient(app) as client:
        yield client


def _join(client: TestClient, match_id: str, name: str) -> str:
    return str(
        client.post("/api/v1/lobby/join", json={"match_id": match_id, "player_name": name}).json()[
            "token"
        ]
    )


# --- transport-free unit checks ---
async def test_session_acts_only_on_its_turn() -> None:
    profile = AgentProfile.load_from_yaml("profiles/aggressive.yml")
    llm = AsyncMock()
    session = AgentSession(profile, llm, MemoryWindow(5))

    joined = {"event": "joined", "payload": {"symbol": "O", "current_turn": "X",
                                             "board": [""] * 9, "valid_moves": list(range(9))}}
    assert await session.on_event(joined) == []  # not my turn
    llm.generate_structured_response.assert_not_awaited()

    terminal = {"event": "state_update", "payload": {"board": ["X"] + [""] * 8,
                "current_turn": None, "valid_moves": [], "last_move": {"player": "X", "move": 0}}}
    assert await session.on_event(terminal) == []  # terminal update -> never act
    llm.generate_structured_response.assert_not_awaited()


async def test_game_over_sets_finished() -> None:
    profile = AgentProfile.load_from_yaml("profiles/aggressive.yml")
    session = AgentSession(profile, AsyncMock(), MemoryWindow(5))
    await session.on_event({"event": "game_over", "payload": {"result": "draw"}})
    assert session.finished is True


# --- full game to game_over over the real server (v02 gate) ---
async def _feed(ws: Any, session: AgentSession, event: dict[str, Any]) -> None:
    for action in await session.on_event(event):
        ws.send_json(action)


async def test_agent_plays_full_game_to_win(lobby: TestClient) -> None:
    match_id = lobby.post("/api/v1/lobby/match").json()["match_id"]
    x_token = _join(lobby, match_id, "Ironclaw")
    o_token = _join(lobby, match_id, "Scripted")

    profile = AgentProfile.load_from_yaml("profiles/aggressive.yml")
    llm = AsyncMock()
    # 4 real decisions: open 0; an illegal retry (0 now taken) then 1; then the winning 2.
    llm.generate_structured_response = AsyncMock(side_effect=[
        AgentResponse(move=0, comment="mine"),
        AgentResponse(move=0, comment="still mine!"),  # illegal: occupied -> retry
        AgentResponse(move=1, comment="next door"),
        AgentResponse(move=2, comment="top row, all mine"),
    ])
    session = AgentSession(profile, llm, MemoryWindow(profile.memory_limit))
    o_moves = iter([3, 4])  # never blocks the top row

    with lobby.websocket_connect(f"/ws/match/{match_id}?token={x_token}") as wx, \
         lobby.websocket_connect(f"/ws/match/{match_id}?token={o_token}") as wo:
        ev_x = wx.receive_json()
        ev_o = wo.receive_json()
        assert ev_x["payload"]["symbol"] == "X" and ev_o["payload"]["symbol"] == "O"

        await _feed(wx, session, ev_x)  # X opens with move 0

        result_event = None
        for _ in range(4):
            wx.receive_json()   # X's own chat echo
            su_x = wx.receive_json()
            wo.receive_json()   # same chat on O
            su_o = wo.receive_json()
            if su_x["payload"]["current_turn"] is None:  # terminal move
                await _feed(wx, session, su_x)  # must NOT act
                over_x = wx.receive_json()
                over_o = wo.receive_json()
                await _feed(wx, session, over_x)
                result_event = over_x
                assert over_o == over_x
                break
            await _feed(wx, session, su_x)  # not X's turn -> records O's move, no action
            wo.send_json({"action": "submit_move", "payload": {"move": next(o_moves)}})
            su2_x = wx.receive_json()  # O's move broadcast
            wo.receive_json()
            await _feed(wx, session, su2_x)  # X's turn again

    assert result_event == {"event": "game_over", "payload": {"result": "X"}}
    assert session.finished
    # Exactly 4 model calls -- proof neither the terminal update nor game_over triggered a 5th.
    assert llm.generate_structured_response.await_count == 4
    events = session._memory.events()  # noqa: SLF001 -- verifying opponent moves landed in memory
    assert "O played 3" in events and "O played 4" in events
    assert not any("X played" in e for e in events)  # never records its own moves
