import argparse
import asyncio
import json
import os
import sys
from typing import Any

import httpx2
import websockets
from dotenv import load_dotenv

from pydantic import ValidationError

from client.llm import GeminiClient, LLMClient
from client.memory import MemoryWindow
from client.prompt import build_prompt
from client.schemas import AgentResponse

DEFAULT_SERVER_URL = "http://localhost:8000"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent Arena — LLM-powered game agent")
    parser.add_argument("--match-id", required=True, help="Match UUID to join")
    parser.add_argument("--server-url", default=DEFAULT_SERVER_URL, help="Base URL of the game server")
    parser.add_argument("--player-name", default="Gemini-Agent", help="Display name to join the match as")
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
    MemoryWindow of recent events) and routes incoming server events. When
    it's this agent's turn, builds a persona-driven prompt from the memory +
    current board and hits the LLM. Translating the raw LLM response into an
    actual submit_move action is reserved for v03.03."""

    def __init__(self, player_name: str, llm: LLMClient | None = None, memory_limit: int = 10) -> None:
        self.player_name = player_name
        self.symbol: str | None = None
        self.llm = llm
        self.memory = MemoryWindow(maxlen=memory_limit)

    def is_my_turn(self, current_turn: Any) -> bool:
        return self.symbol is not None and self.symbol == current_turn

    async def on_my_turn(self, payload: dict[str, Any]) -> None:
        board = payload.get("board", [])
        valid_moves = payload.get("valid_moves", [])
        print(f"[{self.player_name}] It's my turn. valid_moves={valid_moves}")
        if self.llm is None:
            return

        prompt = build_prompt(self.memory, board, valid_moves)
        try:
            agent_response = await self.llm.generate_structured_response(prompt, AgentResponse)
        except (ValueError, ValidationError) as exc:
            print(f"[{self.player_name}] Failed to parse LLM response as AgentResponse: {exc}", file=sys.stderr)
            return

        print(f"[{self.player_name}] LLM chose move={agent_response.move} comment={agent_response.comment!r}")

    async def handle_event(self, event: dict[str, Any]) -> None:
        kind = event.get("event")
        payload = event.get("payload", {})

        if kind == "joined":
            self.symbol = payload.get("symbol")
            print(f"[{self.player_name}] Joined as '{self.symbol}'. Board: {payload.get('board')}")
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
        async for raw_message in websocket:
            try:
                event = json.loads(raw_message)
            except json.JSONDecodeError:
                print(f"[{session.player_name}] Received malformed message from server, skipping", file=sys.stderr)
                continue
            await session.handle_event(event)


async def run(args: argparse.Namespace, api_key: str) -> None:
    token = await join_match(args.server_url, args.match_id, args.player_name)
    print(f"Joined match {args.match_id} as {args.player_name}. Auth token acquired.")
    session = AgentSession(args.player_name, llm=GeminiClient(api_key=api_key))
    await run_event_loop(args.server_url, args.match_id, token, session)


def main() -> None:
    api_key = require_gemini_api_key()
    args = parse_args()
    asyncio.run(run(args, api_key))


if __name__ == "__main__":
    main()
