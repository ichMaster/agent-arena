"""Integration: AgentSession plays a FULL game against the real server (v02 release gate).

The LLM is a scripted mock (incl. one illegal reply → retry) — zero paid calls. The agent's events
flow through a real TestClient WebSocket against the real app + throwaway DB; a scripted opponent
holds the second seat. Verifies: acts only on its own turn, never on the terminal `state_update`
(current_turn null), records opponent moves + chat, finishes cleanly on `game_over`.
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
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/agent.db")
    app = create_app(db_engine=engine, session_maker=create_session_maker(engine))
    with TestClient(app) as client:
        yield client


def _join(client: TestClient, match_id: str, name: str) -> str:
    body = {"match_id": match_id, "player_name": name}
    return str(client.post("/api/v1/lobby/join", json=body).json()["token"])


def _step(ws: Any, session: AgentSession) -> dict[str, Any]:
    """Feed one server event through the session; send any produced actions back on the socket."""
    event: dict[str, Any] = ws.receive_json()
    for action in asyncio.run(session.on_event(event)):
        ws.send_json(action)
    return event


def test_agent_plays_full_game_to_win(lobby: TestClient) -> None:
    match_id = lobby.post("/api/v1/lobby/match").json()["match_id"]
    agent_token = _join(lobby, match_id, "Blaze")
    opp_token = _join(lobby, match_id, "Rival")

    profile = AgentProfile.load_from_yaml("profiles/aggressive.yml")
    # Scripted model: 0 (legal) · 0 (ILLEGAL — occupied, forces a retry) · 1 · 2 → X wins top row.
    llm = AsyncMock()
    llm.generate_structured_response = AsyncMock(
        side_effect=[
            AgentResponse(move=0, comment="corner, obviously"),
            AgentResponse(move=0, comment="again!"),        # illegal: cell 0 now occupied
            AgentResponse(move=1, comment="fine, next door"),
            AgentResponse(move=2, comment="top row, done"),
        ]
    )
    memory = MemoryWindow(profile.memory_limit)
    session = AgentSession(profile, llm, memory)

    with lobby.websocket_connect(f"/ws/match/{match_id}?token={agent_token}") as wa:
        _step(wa, session)                    # joined as X, my turn -> chat+submit (LLM call 1)
        _step(wa, session)                    # own chat_message (skipped)
        _step(wa, session)                    # state_update, turn O -> no act
        with lobby.websocket_connect(f"/ws/match/{match_id}?token={opp_token}") as wo:
            wo.receive_json()                 # opponent joined as O

            wo.send_json({"action": "chat", "payload": {"message": "you're toast"}})
            _step(wa, session)                # opponent chat -> recorded
            wo.receive_json()                 # opponent drains own chat

            wo.send_json({"action": "submit_move", "payload": {"move": 3}})
            _step(wa, session)                # state_update, my turn -> LLM calls 2+3 (retry) -> move 1
            wo.receive_json()                 # opponent drains state_update
            _step(wa, session)                # own chat_message
            _step(wa, session)                # state_update, turn O
            wo.receive_json(); wo.receive_json()  # opponent drains agent chat + state

            wo.send_json({"action": "submit_move", "payload": {"move": 4}})
            _step(wa, session)                # state_update, my turn -> LLM call 4 -> move 2 (win)
            wo.receive_json()                 # opponent drains state_update
            _step(wa, session)                # own chat_message
            terminal = _step(wa, session)     # TERMINAL state_update: current_turn null -> no act
            over = _step(wa, session)         # game_over

    assert terminal["event"] == "state_update" and terminal["payload"]["current_turn"] is None
    assert over == {"event": "game_over", "payload": {"result": "X"}}
    assert session.finished
    # Exactly 4 model calls: the terminal update and game_over triggered no extra decision.
    assert llm.generate_structured_response.await_count == 4
    # Opponent's moves and chat were remembered; the agent's own were not double-recorded.
    events = memory.events()
    assert "O played 3" in events and "O played 4" in events
    assert 'O said: "you\'re toast"' in events


def test_session_never_acts_off_turn_or_terminal() -> None:
    profile = AgentProfile.load_from_yaml("profiles/aggressive.yml")
    llm = AsyncMock()
    session = AgentSession(profile, llm, MemoryWindow(5))
    asyncio.run(session.on_event({"event": "joined", "payload": {
        "symbol": "O", "board": [""] * 9, "current_turn": "X", "valid_moves": list(range(9))}}))
    actions = asyncio.run(session.on_event({"event": "state_update", "payload": {
        "board": ["X"] + [""] * 8, "current_turn": None, "valid_moves": [],
        "last_move": {"player": "X", "move": 0}}}))
    assert actions == []
    llm.generate_structured_response.assert_not_awaited()


def test_observer_symbol_null_never_moves() -> None:
    profile = AgentProfile.load_from_yaml("profiles/aggressive.yml")
    llm = AsyncMock()
    session = AgentSession(profile, llm, MemoryWindow(5))
    actions = asyncio.run(session.on_event({"event": "joined", "payload": {
        "symbol": None, "board": [""] * 9, "current_turn": "X", "valid_moves": list(range(9))}}))
    assert actions == []
    llm.generate_structured_response.assert_not_awaited()
