import argparse
import asyncio
import os
import sys

import httpx2
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


async def run(args: argparse.Namespace) -> None:
    token = await join_match(args.server_url, args.match_id, args.player_name)
    print(f"Joined match {args.match_id} as {args.player_name}. Auth token acquired.")


def main() -> None:
    require_gemini_api_key()
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
