import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx2
import pytest
import uvicorn
import websockets
from pydantic import ValidationError

from client.agent import (
    MAX_MOVE_ATTEMPTS,
    AgentSession,
    join_match,
    parse_args,
    require_gemini_api_key,
    run,
    run_event_loop,
    to_ws_url,
)
from client.schemas import AgentResponse
from server.main import app


class FakeClientWebSocket:
    """Stands in for a `websockets` client connection — only the `.send()`
    surface AgentSession actually uses."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, raw_text: str) -> None:
        self.sent.append(json.loads(raw_text))


def test_parse_args_reads_required_and_optional_fields() -> None:
    args = parse_args(["--match-id", "abc-123", "--profile", "profiles/aggressive_bot.yml"])
    assert args.match_id == "abc-123"
    assert args.server_url == "http://localhost:8000"
    assert args.profile == "profiles/aggressive_bot.yml"
    assert args.symbol is None
    assert args.player_name is None

    args = parse_args(
        [
            "--match-id",
            "abc-123",
            "--server-url",
            "http://example.com",
            "--profile",
            "profiles/cowardly_bot.yml",
            "--symbol",
            "O",
            "--player-name",
            "Bot",
        ]
    )
    assert args.server_url == "http://example.com"
    assert args.symbol == "O"
    assert args.player_name == "Bot"


def test_parse_args_requires_match_id() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--profile", "profiles/aggressive_bot.yml"])


def test_parse_args_requires_profile() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--match-id", "abc-123"])


def test_parse_args_rejects_invalid_symbol() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--match-id", "abc-123", "--profile", "profiles/aggressive_bot.yml", "--symbol", "Z"])


def test_agent_py_runs_as_a_direct_script() -> None:
    """Regression test: every roadmap issue documents this CLI as
    `python client/agent.py ...` (not `python -m client.agent`), which
    broke once the module started using absolute `client.*` imports —
    running it directly only puts client/ on sys.path, not the project
    root. Exercises the real subprocess, not just an import."""
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, str(repo_root / "client" / "agent.py"), "--help"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        timeout=10,
    )
    assert result.returncode == 0
    assert "No module named" not in result.stderr
    assert "--profile PROFILE" in result.stdout


def test_require_gemini_api_key_exits_when_missing() -> None:
    # Patch out load_dotenv so this test's assertion doesn't depend on whether
    # a real .env file happens to exist on disk with a real GEMINI_API_KEY in it.
    with patch("client.agent.load_dotenv"), patch.dict(os.environ, {}, clear=True):
        with pytest.raises(SystemExit):
            require_gemini_api_key()


def test_require_gemini_api_key_returns_value_when_present() -> None:
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-123"}):
        assert require_gemini_api_key() == "test-key-123"


async def test_run_loads_profile_and_wires_agent_session() -> None:
    args = parse_args(
        ["--match-id", "match-1", "--profile", "profiles/aggressive_bot.yml", "--symbol", "X"]
    )
    captured: dict = {}

    async def fake_run_event_loop(server_url, match_id, token, session):
        captured["session"] = session

    with (
        patch("client.agent.join_match", new=AsyncMock(return_value="tok-123")) as fake_join,
        patch("client.agent.run_event_loop", new=fake_run_event_loop),
        patch("client.agent.create_llm_client") as fake_create_llm_client,
    ):
        await run(args, api_key="fake-key")

    fake_join.assert_awaited_once_with(args.server_url, "match-1", "Aggressor-Prime")
    fake_create_llm_client.assert_called_once_with("gemini-3.1-pro", "fake-key", 1.1)

    session = captured["session"]
    assert session.player_name == "Aggressor-Prime"
    assert session.expected_symbol == "X"
    assert "ruthlessly aggressive" in session.persona
    assert session.memory._events.maxlen == 10


async def test_run_lets_player_name_override_profile_name() -> None:
    args = parse_args(
        [
            "--match-id",
            "match-1",
            "--profile",
            "profiles/cowardly_bot.yml",
            "--player-name",
            "Custom-Name",
        ]
    )
    captured: dict = {}

    async def fake_run_event_loop(server_url, match_id, token, session):
        captured["session"] = session

    with (
        patch("client.agent.join_match", new=AsyncMock(return_value="tok-123")) as fake_join,
        patch("client.agent.run_event_loop", new=fake_run_event_loop),
        patch("client.agent.create_llm_client"),
    ):
        await run(args, api_key="fake-key")

    fake_join.assert_awaited_once_with(args.server_url, "match-1", "Custom-Name")
    assert captured["session"].player_name == "Custom-Name"


async def test_join_match_returns_token_from_real_app() -> None:
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as setup_client:
        match_response = await setup_client.post("/api/v1/lobby/match")
        match_id = match_response.json()["match_id"]

    token = await join_match("http://test", match_id, "Ada", transport=transport)
    assert isinstance(token, str)
    assert len(token) > 0


async def test_join_match_exits_on_connection_error() -> None:
    with pytest.raises(SystemExit):
        await join_match("http://127.0.0.1:1", "some-match", "Ada")


def test_to_ws_url_converts_http_scheme_and_appends_path() -> None:
    assert to_ws_url("http://localhost:8000", "match-1", "tok") == "ws://localhost:8000/ws/match/match-1?token=tok"


def test_to_ws_url_converts_https_scheme() -> None:
    assert to_ws_url("https://arena.example.com", "match-1", "tok") == (
        "wss://arena.example.com/ws/match/match-1?token=tok"
    )


async def test_agent_session_learns_symbol_from_joined_event() -> None:
    session = AgentSession("Ada")
    assert session.symbol is None
    await session.handle_event({"event": "joined", "payload": {"symbol": "X", "board": [None] * 9, "current_turn": "X"}})
    assert session.symbol == "X"


async def test_agent_session_uses_custom_persona_in_prompt(capsys) -> None:
    fake_llm = AsyncMock()
    fake_llm.generate_structured_response.return_value = AgentResponse(move=0, comment="Eek, if I must.")
    session = AgentSession("Nervous-Nelly", llm=fake_llm, persona="You are a nervous, defensive player.")
    session.symbol = "X"
    session.websocket = FakeClientWebSocket()

    await session.handle_event(
        {"event": "state_update", "payload": {"board": [None] * 9, "current_turn": "X", "valid_moves": [0]}}
    )

    prompt = fake_llm.generate_structured_response.await_args.args[0]
    assert "You are a nervous, defensive player." in prompt
    assert "arrogant Tic-Tac-Toe master" not in prompt


async def test_agent_session_warns_on_symbol_mismatch(capsys) -> None:
    session = AgentSession("Ada", expected_symbol="O")
    await session.handle_event(
        {"event": "joined", "payload": {"symbol": "X", "board": [None] * 9, "current_turn": "O"}}
    )
    assert session.symbol == "X"  # the server's assignment always wins
    captured = capsys.readouterr()
    assert "expected symbol 'O'" in captured.err
    assert "assigned 'X'" in captured.err


async def test_agent_session_no_warning_when_symbol_matches_expected(capsys) -> None:
    session = AgentSession("Ada", expected_symbol="X")
    await session.handle_event(
        {"event": "joined", "payload": {"symbol": "X", "board": [None] * 9, "current_turn": "O"}}
    )
    captured = capsys.readouterr()
    assert "WARNING" not in captured.err


async def test_agent_session_detects_its_turn_from_state_update() -> None:
    session = AgentSession("Ada")
    session.symbol = "O"
    turns_taken = []

    async def fake_on_my_turn(payload: dict) -> None:
        turns_taken.append(payload)

    session.on_my_turn = fake_on_my_turn  # type: ignore[method-assign]

    await session.handle_event({"event": "state_update", "payload": {"board": [None] * 9, "current_turn": "X"}})
    assert turns_taken == []

    await session.handle_event({"event": "state_update", "payload": {"board": [None] * 9, "current_turn": "O"}})
    assert len(turns_taken) == 1


async def test_agent_session_ignores_events_before_symbol_is_known() -> None:
    session = AgentSession("Ada")
    called = []

    async def fake_on_my_turn(payload: dict) -> None:
        called.append(payload)

    session.on_my_turn = fake_on_my_turn  # type: ignore[method-assign]
    # current_turn happens to be None (matching an unset symbol) — must not trigger a turn.
    await session.handle_event({"event": "state_update", "payload": {"current_turn": None}})
    assert called == []


async def test_agent_session_records_chat_and_moves_into_memory() -> None:
    session = AgentSession("Ada")
    await session.handle_event({"event": "chat_message", "payload": {"sender": "Bob", "message": "gl hf"}})
    await session.handle_event(
        {
            "event": "state_update",
            "payload": {"board": ["X"] + [None] * 8, "current_turn": "O", "last_move": {"player": "X", "move": 0}},
        }
    )
    lines = session.memory.as_lines()
    assert "- [chat] Bob: gl hf" in lines
    assert "- [move] Player X played cell 0" in lines


async def test_agent_session_calls_llm_with_built_prompt_on_its_turn() -> None:
    fake_llm = AsyncMock()
    fake_llm.generate_structured_response.return_value = AgentResponse(move=4, comment="The center is mine.")
    session = AgentSession("Ada", llm=fake_llm)
    session.symbol = "X"
    session.websocket = FakeClientWebSocket()

    await session.handle_event(
        {
            "event": "state_update",
            "payload": {"board": [None] * 9, "current_turn": "X", "valid_moves": list(range(9))},
        }
    )

    fake_llm.generate_structured_response.assert_awaited_once()
    prompt, schema = fake_llm.generate_structured_response.await_args.args
    assert "arrogant Tic-Tac-Toe master" in prompt
    assert schema is AgentResponse
    assert "Valid moves: [0, 1, 2, 3, 4, 5, 6, 7, 8]" in prompt


async def test_agent_session_without_llm_does_not_crash_on_its_turn() -> None:
    session = AgentSession("Ada")  # llm=None, matching the pre-v03.02 default
    session.symbol = "X"
    await session.handle_event(
        {"event": "state_update", "payload": {"board": [None] * 9, "current_turn": "X", "valid_moves": [0]}}
    )


async def test_agent_session_handles_malformed_llm_response_without_crashing() -> None:
    fake_llm = AsyncMock()
    fake_llm.generate_structured_response.side_effect = ValidationError.from_exception_data(
        "AgentResponse", [{"type": "missing", "loc": ("move",), "input": {}}]
    )
    session = AgentSession("Ada", llm=fake_llm)
    session.symbol = "X"
    session.websocket = FakeClientWebSocket()

    # Must not raise — a parse failure is logged and swallowed, not fatal.
    await session.handle_event(
        {"event": "state_update", "payload": {"board": [None] * 9, "current_turn": "X", "valid_moves": [0]}}
    )


async def test_on_my_turn_sends_chat_then_submit_move_over_the_websocket() -> None:
    fake_llm = AsyncMock()
    fake_llm.generate_structured_response.return_value = AgentResponse(move=4, comment="Behold my dominance.")
    session = AgentSession("Ada", llm=fake_llm)
    session.symbol = "X"
    fake_ws = FakeClientWebSocket()
    session.websocket = fake_ws

    await session.handle_event(
        {"event": "state_update", "payload": {"board": [None] * 9, "current_turn": "X", "valid_moves": [4]}}
    )

    assert fake_ws.sent == [
        {"action": "chat", "payload": {"message": "Behold my dominance."}},
        {"action": "submit_move", "payload": {"move": 4}},
    ]


async def test_decide_move_accepts_a_valid_first_response() -> None:
    fake_llm = AsyncMock()
    fake_llm.generate_structured_response.return_value = AgentResponse(move=4, comment="Center, obviously.")
    session = AgentSession("Ada", llm=fake_llm)

    result = await session._decide_move(board=[None] * 9, valid_moves=list(range(9)))

    assert result.move == 4
    assert fake_llm.generate_structured_response.await_count == 1


async def test_decide_move_retries_after_an_invalid_move_then_succeeds() -> None:
    fake_llm = AsyncMock()
    fake_llm.generate_structured_response.side_effect = [
        AgentResponse(move=99, comment="I'll take the corner."),  # invalid: not in valid_moves
        AgentResponse(move=4, comment="Fine, the center then."),
    ]
    session = AgentSession("Ada", llm=fake_llm)

    result = await session._decide_move(board=[None] * 9, valid_moves=[4, 5, 6])

    assert result.move == 4
    assert fake_llm.generate_structured_response.await_count == 2
    second_prompt = fake_llm.generate_structured_response.await_args_list[1].args[0]
    assert "Move 99 is invalid" in second_prompt
    assert "[4, 5, 6]" in second_prompt


async def test_decide_move_falls_back_to_random_valid_move_after_exhausting_attempts() -> None:
    fake_llm = AsyncMock()
    fake_llm.generate_structured_response.return_value = AgentResponse(move=99, comment="Corner!")
    session = AgentSession("Ada", llm=fake_llm)

    result = await session._decide_move(board=[None] * 9, valid_moves=[7])

    assert result.move == 7  # only one legal option, so the fallback is deterministic here
    assert fake_llm.generate_structured_response.await_count == MAX_MOVE_ATTEMPTS


async def test_decide_move_falls_back_after_repeated_unparseable_responses() -> None:
    fake_llm = AsyncMock()
    fake_llm.generate_structured_response.side_effect = ValidationError.from_exception_data(
        "AgentResponse", [{"type": "missing", "loc": ("move",), "input": {}}]
    )
    session = AgentSession("Ada", llm=fake_llm)

    result = await session._decide_move(board=[None] * 9, valid_moves=[3])

    assert result.move == 3
    assert fake_llm.generate_structured_response.await_count == MAX_MOVE_ATTEMPTS


async def test_on_my_turn_skips_llm_when_no_valid_moves() -> None:
    fake_llm = AsyncMock()
    session = AgentSession("Ada", llm=fake_llm)
    session.symbol = "X"

    await session.handle_event(
        {"event": "state_update", "payload": {"board": ["X"] * 9, "current_turn": "X", "valid_moves": []}}
    )

    fake_llm.generate_structured_response.assert_not_awaited()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def live_server():
    """Runs the real FastAPI app under real uvicorn on a background thread,
    bound to loopback — needed because the `websockets` client library speaks
    raw ws:// over a socket and can't be pointed at an ASGI transport."""
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", lifespan="on")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:
        raise RuntimeError("live_server did not start in time")

    yield base_url

    server.should_exit = True
    thread.join(timeout=5)


async def test_agent_completes_full_game_over_real_websocket(live_server: str) -> None:
    async with httpx2.AsyncClient(base_url=live_server, timeout=10.0) as http_client:
        match_id = (await http_client.post("/api/v1/lobby/match")).json()["match_id"]

    ada_token = await join_match(live_server, match_id, "Ada")
    bob_token = await join_match(live_server, match_id, "Bob")

    ada_session, bob_session = AgentSession("Ada"), AgentSession("Bob")
    ada_ws_url = to_ws_url(live_server, match_id, ada_token)
    bob_ws_url = to_ws_url(live_server, match_id, bob_token)

    async with websockets.connect(ada_ws_url) as ada_ws, websockets.connect(bob_ws_url) as bob_ws:
        await ada_session.handle_event(json.loads(await ada_ws.recv()))
        await bob_session.handle_event(json.loads(await bob_ws.recv()))

        # Ada connects first, so she's assigned X and moves first; Bob is O.
        assert ada_session.symbol == "X"
        assert bob_session.symbol == "O"

        # X plays the top row (0,1,2); O plays 3,4 — X wins. Each move's
        # state_update (and the sockets it goes to) is drained after sending
        # so the two connections never fall out of lockstep.
        sequence = [(ada_ws, bob_ws, 0), (bob_ws, ada_ws, 3), (ada_ws, bob_ws, 1), (bob_ws, ada_ws, 4), (ada_ws, bob_ws, 2)]
        for mover_ws, other_ws, move in sequence:
            await mover_ws.send(json.dumps({"action": "submit_move", "payload": {"move": move}}))
            assert json.loads(await mover_ws.recv())["event"] == "state_update"
            assert json.loads(await other_ws.recv())["event"] == "state_update"

        ada_final = json.loads(await ada_ws.recv())
        bob_final = json.loads(await bob_ws.recv())
        assert ada_final == {"event": "game_over", "payload": {"result": "X"}}
        assert bob_final == ada_final


async def test_agent_autonomously_sends_move_over_real_websocket_on_its_turn(live_server: str) -> None:
    async with httpx2.AsyncClient(base_url=live_server, timeout=10.0) as http_client:
        match_id = (await http_client.post("/api/v1/lobby/match")).json()["match_id"]
    token = await join_match(live_server, match_id, "Agent")

    fake_llm = AsyncMock()
    fake_llm.generate_structured_response.return_value = AgentResponse(move=4, comment="I'll start in the center.")
    session = AgentSession("Agent", llm=fake_llm)

    async with websockets.connect(to_ws_url(live_server, match_id, token)) as ws:
        session.websocket = ws
        joined = json.loads(await ws.recv())
        assert joined["event"] == "joined"

        # Agent is assigned X (first to connect) and X moves first, so
        # handling its own "joined" event triggers on_my_turn immediately.
        await session.handle_event(joined)

        chat_echo = json.loads(await ws.recv())
        move_echo = json.loads(await ws.recv())

    assert chat_echo == {
        "event": "chat_message",
        "payload": {"sender": "Agent", "message": "I'll start in the center."},
    }
    assert move_echo["event"] == "state_update"
    assert move_echo["payload"]["board"][4] == "X"
    assert move_echo["payload"]["last_move"] == {"player": "X", "move": 4}


async def test_run_event_loop_connects_and_routes_the_joined_event(live_server: str) -> None:
    async with httpx2.AsyncClient(base_url=live_server, timeout=10.0) as http_client:
        match_id = (await http_client.post("/api/v1/lobby/match")).json()["match_id"]
    token = await join_match(live_server, match_id, "Ada")

    session = AgentSession("Ada")
    task = asyncio.create_task(run_event_loop(live_server, match_id, token, session))
    try:
        deadline = time.monotonic() + 5
        while session.symbol is None and time.monotonic() < deadline:
            await asyncio.sleep(0.02)
        assert session.symbol == "X"
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
