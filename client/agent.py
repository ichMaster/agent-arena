import argparse
import asyncio
import json
import os
import sys
from typing import Any

import httpx2
import websockets
from dotenv import load_dotenv

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
    """Tracks per-connection state (this agent's assigned symbol) and routes
    incoming server events. `on_my_turn` is a placeholder here — v03.02/v03.03
    wire it up to the LLM prompt/response pipeline."""

    def __init__(self, player_name: str) -> None:
        self.player_name = player_name
        self.symbol: str | None = None

    def is_my_turn(self, current_turn: Any) -> bool:
        return self.symbol is not None and self.symbol == current_turn

    async def on_my_turn(self, payload: dict[str, Any]) -> None:
        print(f"[{self.player_name}] It's my turn. valid_moves={payload.get('valid_moves')}")

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
        elif kind == "chat_message":
            print(f"[{self.player_name}] chat from {payload.get('sender')}: {payload.get('message')}")
        elif kind == "game_over":
            print(f"[{self.player_name}] Game over. Result: {payload.get('result')}")
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


async def run(args: argparse.Namespace) -> None:
    token = await join_match(args.server_url, args.match_id, args.player_name)
    print(f"Joined match {args.match_id} as {args.player_name}. Auth token acquired.")
    session = AgentSession(args.player_name)
    await run_event_loop(args.server_url, args.match_id, token, session)


def main() -> None:
    require_gemini_api_key()
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
