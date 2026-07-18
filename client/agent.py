import argparse
import asyncio
import json
import os
import random
import sys
from pathlib import Path
from typing import Any

# Every roadmap issue documents this CLI as `python client/agent.py ...` (a
# direct script invocation), but the module below imports its siblings as
# `client.llm`, `client.memory`, etc. Running the file directly puts only
# `client/` on sys.path, not the project root, so those absolute imports
# would fail with "No module named 'client'". Adding the project root here
# (skipped when this is imported normally, e.g. `from client.agent import
# ...` in tests, since __package__ is then non-empty) makes both work.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx2
import websockets
from dotenv import load_dotenv

from pydantic import ValidationError

from client.llm import LLMClient, create_llm_client
from client.memory import MemoryWindow
from client.profile import AgentProfile
from client.prompt import SYSTEM_PERSONA, build_prompt
from client.schemas import AgentResponse

DEFAULT_SERVER_URL = "http://localhost:8000"
MAX_MOVE_ATTEMPTS = 3


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent Arena — LLM-powered game agent")
    parser.add_argument("--match-id", required=True, help="Match UUID to join")
    parser.add_argument("--server-url", default=DEFAULT_SERVER_URL, help="Base URL of the game server")
    parser.add_argument("--profile", required=True, help="Path to an AgentProfile YAML file")
    parser.add_argument(
        "--symbol",
        choices=["X", "O"],
        default=None,
        help="Symbol this agent expects to play as; the server actually assigns it by connection "
        "order, so this only warns on mismatch rather than forcing an assignment",
    )
    parser.add_argument(
        "--player-name", default=None, help="Override the display name (defaults to the profile's name)"
    )
    return parser.parse_args(argv)


def require_gemini_api_key() -> str:
    """Loads .env and returns GEMINI_API_KEY, or aborts startup with a clear
    error — the agent must never proceed with a missing/None key that would
    otherwise fail silently deep inside a later LLM call."""
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print(
            "ERROR: GEMINI_API_KEY is not set. Add it to a .env file or export it before running the agent.",
            file=sys.stderr,
        )
        sys.exit(1)
    return api_key


async def join_match(
    server_url: str, match_id: str, player_name: str, transport: httpx2.AsyncBaseTransport | None = None
) -> str:
    async with httpx2.AsyncClient(base_url=server_url, timeout=10.0, transport=transport) as http_client:
        try:
            response = await http_client.post(
                "/api/v1/lobby/join", json={"match_id": match_id, "player_name": player_name}
            )
            response.raise_for_status()
        except httpx2.ConnectError as exc:
            print(f"ERROR: Could not reach server at {server_url}: {exc}", file=sys.stderr)
            sys.exit(1)
        except httpx2.HTTPStatusError as exc:
            print(
                f"ERROR: Server rejected join request ({exc.response.status_code}): {exc.response.text}",
                file=sys.stderr,
            )
            sys.exit(1)
        return str(response.json()["token"])


def to_ws_url(server_url: str, match_id: str, token: str) -> str:
    ws_scheme_url = server_url.replace("https://", "wss://").replace("http://", "ws://")
    return f"{ws_scheme_url}/ws/match/{match_id}?token={token}"


class AgentSession:
    """Tracks per-connection state (this agent's assigned symbol, a rolling
    MemoryWindow of recent events, and the live websocket) and routes
    incoming server events. When it's this agent's turn, builds a
    persona-driven prompt, asks the LLM for a move, and transmits it (plus
    its trash-talk) back to the server."""

    def __init__(
        self,
        player_name: str,
        llm: LLMClient | None = None,
        memory_limit: int = 10,
        persona: str = SYSTEM_PERSONA,
        expected_symbol: str | None = None,
    ) -> None:
        self.player_name = player_name
        self.symbol: str | None = None
        self.llm = llm
        self.memory = MemoryWindow(maxlen=memory_limit)
        self.persona = persona
        self.expected_symbol = expected_symbol
        self.websocket: Any = None  # set by run_event_loop once connected

    def is_my_turn(self, current_turn: Any) -> bool:
        return self.symbol is not None and self.symbol == current_turn

    async def _send(self, action: str, payload: dict[str, Any]) -> None:
        assert self.websocket is not None
        await self.websocket.send(json.dumps({"action": action, "payload": payload}))

    async def on_my_turn(self, payload: dict[str, Any]) -> None:
        board = payload.get("board", [])
        valid_moves = payload.get("valid_moves", [])
        print(f"[{self.player_name}] It's my turn. valid_moves={valid_moves}")
        if self.llm is None or not valid_moves:
            return

        agent_response = await self._decide_move(board, valid_moves)
        print(f"[{self.player_name}] Decided move={agent_response.move} comment={agent_response.comment!r}")

        await self._send("chat", {"message": agent_response.comment})
        await self._send("submit_move", {"move": agent_response.move})

    async def _decide_move(self, board: list[Any], valid_moves: list[int]) -> AgentResponse:
        """Asks the LLM for a move, retrying up to MAX_MOVE_ATTEMPTS times if it
        hallucinates an out-of-bounds/occupied cell or returns unparseable JSON.
        Falls back to a random valid move rather than stalling the game."""
        assert self.llm is not None
        base_prompt = build_prompt(self.memory, board, valid_moves, self.persona)
        prompt = base_prompt
        last_comment = ""

        for attempt in range(1, MAX_MOVE_ATTEMPTS + 1):
            try:
                agent_response = await self.llm.generate_structured_response(prompt, AgentResponse)
            except (ValueError, ValidationError) as exc:
                print(f"[{self.player_name}] Attempt {attempt}: unparseable LLM response: {exc}", file=sys.stderr)
                prompt = f"{prompt}\n\nYour previous reply could not be parsed. Respond with valid JSON only."
                continue

            if agent_response.move in valid_moves:
                return agent_response

            print(
                f"[{self.player_name}] Attempt {attempt}: move {agent_response.move} is invalid.", file=sys.stderr
            )
            last_comment = agent_response.comment
            prompt = (
                f"{base_prompt}\n\n"
                f"Error: Move {agent_response.move} is invalid. The valid moves are {valid_moves}. Try again."
            )

        fallback_move = random.choice(valid_moves)
        print(f"[{self.player_name}] Exhausted {MAX_MOVE_ATTEMPTS} attempts; falling back to move {fallback_move}.")
        return AgentResponse(move=fallback_move, comment=last_comment or "Fine. I'll play here.")

    async def handle_event(self, event: dict[str, Any]) -> None:
        kind = event.get("event")
        payload = event.get("payload", {})

        if kind == "joined":
            self.symbol = payload.get("symbol")
            print(f"[{self.player_name}] Joined as '{self.symbol}'. Board: {payload.get('board')}")
            if self.expected_symbol is not None and self.symbol != self.expected_symbol:
                print(
                    f"[{self.player_name}] WARNING: expected symbol '{self.expected_symbol}' via --symbol, "
                    f"but the server assigned '{self.symbol}' (assignment is by connection order).",
                    file=sys.stderr,
                )
        elif kind == "state_update":
            print(
                f"[{self.player_name}] state_update: board={payload.get('board')} "
                f"current_turn={payload.get('current_turn')}"
            )
            last_move = payload.get("last_move")
            if last_move:
                self.memory.record("move", f"Player {last_move.get('player')} played cell {last_move.get('move')}")
        elif kind == "chat_message":
            sender, message = payload.get("sender"), payload.get("message")
            print(f"[{self.player_name}] chat from {sender}: {message}")
            self.memory.record("chat", f"{sender}: {message}")
        elif kind == "game_over":
            print(f"[{self.player_name}] Game over. Result: {payload.get('result')}")
            self.memory.record("game_over", f"Result: {payload.get('result')}")
        elif kind == "error":
            print(f"[{self.player_name}] Server error: {payload.get('detail')}", file=sys.stderr)
            return
        else:
            print(f"[{self.player_name}] Unknown event type: {kind!r}", file=sys.stderr)
            return

        if kind in ("joined", "state_update") and self.is_my_turn(payload.get("current_turn")):
            await self.on_my_turn(payload)


async def run_event_loop(server_url: str, match_id: str, token: str, session: AgentSession) -> None:
    ws_url = to_ws_url(server_url, match_id, token)
    async with websockets.connect(ws_url) as websocket:
        session.websocket = websocket
        async for raw_message in websocket:
            try:
                event = json.loads(raw_message)
            except json.JSONDecodeError:
                print(f"[{session.player_name}] Received malformed message from server, skipping", file=sys.stderr)
                continue
            await session.handle_event(event)


async def run(args: argparse.Namespace, api_key: str) -> None:
    profile = AgentProfile.load_from_yaml(args.profile)
    player_name = args.player_name or profile.name

    token = await join_match(args.server_url, args.match_id, player_name)
    print(f"Joined match {args.match_id} as {player_name} (profile: {profile.name}). Auth token acquired.")

    session = AgentSession(
        player_name,
        llm=create_llm_client(profile.model_type, api_key, profile.temperature),
        memory_limit=profile.memory_limit,
        persona=profile.system_prompt,
        expected_symbol=args.symbol,
    )
    await run_event_loop(args.server_url, args.match_id, token, session)


def main() -> None:
    # Line-buffer stdout/stderr explicitly. When stdout is redirected to a
    # file/pipe rather than a TTY (e.g. the swarm script's `>log 2>&1`),
    # Python block-buffers it by default — while stderr stays unbuffered —
    # so a status print like "Joined as 'O'..." can sit unflushed in memory
    # for a long time. That broke both the swarm script's connection-wait
    # (grepping the log for that exact line) and its final `tail -f` (nothing
    # to tail until the buffer happens to fill or the process exits).
    # sys.stdout/stderr are typed as the narrower `TextIO`, which doesn't
    # declare .reconfigure() even though the real runtime type (io.TextIOWrapper)
    # always has it for a normal Python process — a known typeshed gap.
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
    sys.stderr.reconfigure(line_buffering=True)  # type: ignore[union-attr]

    api_key = require_gemini_api_key()
    args = parse_args()
    asyncio.run(run(args, api_key))


if __name__ == "__main__":
    main()
