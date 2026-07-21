"""Agent-vs-agent end-to-end over the real server (ARENA-OPUS-036, §11) — the v04 headline scenario.

Two real AgentSessions (Blaze X + Bastion O) play a scripted, deterministic game to game_over through
the real FastAPI app over real TestClient WebSockets. Both LLMs are mocked (also enforced by the
autouse guard) — zero paid calls.
"""

import asyncio
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
    return str(client.post("/api/v1/lobby/join",
                           json={"match_id": match_id, "player_name": name}).json()["token"])


def _session(profile_path: str, moves: list[int]) -> AgentSession:
    profile = AgentProfile.load_from_yaml(profile_path)
    llm = AsyncMock()
    llm.generate_structured_response = AsyncMock(
        side_effect=[AgentResponse(move=m, comment=f"{profile.name}: {m}") for m in moves]
    )
    return AgentSession(profile, llm, MemoryWindow(profile.memory_limit))


def _feed(ws: Any, session: AgentSession) -> dict[str, Any]:
    """Deliver one event to a session and send back any actions it returns."""
    event: dict[str, Any] = ws.receive_json()
    for action in asyncio.run(session.on_event(event)):
        ws.send_json(action)
    return event


def test_two_agents_play_a_full_game_to_game_over(lobby: TestClient) -> None:
    match_id = lobby.post("/api/v1/lobby/match").json()["match_id"]
    x_token = _join(lobby, match_id, "Blaze")
    o_token = _join(lobby, match_id, "Bastion")

    # X takes the top row (0,1,2) and wins; O plays 3 then 4.
    sX = _session("profiles/aggressive.yml", [0, 1, 2])
    sO = _session("profiles/cautious.yml", [3, 4])

    with lobby.websocket_connect(f"/ws/match/{match_id}?token={x_token}") as wX, \
         lobby.websocket_connect(f"/ws/match/{match_id}?token={o_token}") as wO:
        # Receive BOTH per-socket joined events before acting. If we let X move while processing its
        # joined, that move's broadcast races O's joined (a different server task) and can arrive on
        # O's socket first — so drain both joineds first, then feed the sessions.
        ev_x = wX.receive_json()
        ev_o = wO.receive_json()
        assert ev_x["payload"]["symbol"] == "X"
        assert ev_o["payload"]["symbol"] == "O"
        for action in asyncio.run(sX.on_event(ev_x)):  # X's turn → X opens
            wX.send_json(action)
        for action in asyncio.run(sO.on_event(ev_o)):  # not O's turn → no action
            wO.send_json(action)

        # From here every server event is a broadcast: deliver each to BOTH sockets in order until
        # game_over. Both sockets see the identical broadcast stream, so lock-step draining is safe.
        result_event = None
        for _ in range(40):  # generous bound; the real game ends in ~11 broadcasts
            _feed(wX, sX)
            ev = _feed(wO, sO)
            if ev["event"] == "game_over":
                result_event = ev
                break

    assert result_event == {"event": "game_over", "payload": {"result": "X"}}
    assert sX.finished and sO.finished
    # Each side asked its model exactly the scripted number of times — proof neither acted on the
    # terminal state_update (current_turn null) nor off-turn.
    assert sX._llm.generate_structured_response.await_count == 3  # moves 0,1,2
    assert sO._llm.generate_structured_response.await_count == 2  # moves 3,4
    # Each side remembered the opponent's moves + chat (never its own double-recorded).
    x_mem, o_mem = sX._memory.events(), sO._memory.events()
    assert "O played 3" in x_mem and "O played 4" in x_mem
    assert "X played 0" in o_mem and "X played 1" in o_mem and "X played 2" in o_mem
    assert any("Bastion" in line for line in x_mem)   # heard O's chat
    assert any("Blaze" in line for line in o_mem)     # heard X's chat
