"""Agent Client CLI — joins a match over REST and plays it over one WebSocket (architecture §7.1).

A pure external client: imports nothing from ``server/`` and talks HTTP/WS only, exactly like the Web
UI. The model is reached solely through the ``LLMClient`` seam (always mocked in tests);
``ANTHROPIC_API_KEY`` lives in this process's environment / ``.env`` and is never sent to the server
(§9). Reasoning is printed to line-buffered stdout — read-only observability (§3.2).
"""

import sys
from pathlib import Path

if not __package__:  # direct-run shim: `python agent/agent.py ...` from the repo root
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse  # noqa: E402

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from agent.llm import load_api_key  # noqa: E402
from agent.profile import AgentProfile  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AgentArena agent client (Anthropic Haiku)")
    parser.add_argument("--match-id", required=True, help="the match to join (from the lobby)")
    parser.add_argument("--profile", required=True, help="path to a persona profile YAML")
    parser.add_argument("--server-url", default="http://127.0.0.1:8000")
    parser.add_argument("--player-name", default=None, help="defaults to the profile's name")
    return parser.parse_args(argv)


def load_environment(dotenv_path: str | Path | None = None) -> str:
    """Load ``.env`` then the fail-fast key read — the secret stays here (§9)."""
    load_dotenv(dotenv_path)
    return load_api_key()


async def join_match(
    server_url: str, match_id: str, player_name: str, *, client: httpx.AsyncClient | None = None
) -> str:
    """``POST /lobby/join`` → the seat-bearing token; a clear error if the match is unknown."""
    owns_client = client is None
    http = client if client is not None else httpx.AsyncClient()
    try:
        response = await http.post(
            f"{server_url}/api/v1/lobby/join",
            json={"match_id": match_id, "player_name": player_name},
        )
        if response.status_code == 404:
            raise RuntimeError(f"match {match_id!r} not found on {server_url}")
        response.raise_for_status()
        return str(response.json()["token"])
    finally:
        if owns_client:
            await http.aclose()
