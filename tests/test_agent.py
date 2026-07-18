import os
from unittest.mock import patch

import httpx2
import pytest

from client.agent import join_match, parse_args, require_gemini_api_key
from server.main import app


def test_parse_args_reads_required_and_optional_fields() -> None:
    args = parse_args(["--match-id", "abc-123"])
    assert args.match_id == "abc-123"
    assert args.server_url == "http://localhost:8000"
    assert args.player_name == "Gemini-Agent"

    args = parse_args(
        ["--match-id", "abc-123", "--server-url", "http://example.com", "--player-name", "Bot"]
    )
    assert args.server_url == "http://example.com"
    assert args.player_name == "Bot"


def test_parse_args_requires_match_id() -> None:
    with pytest.raises(SystemExit):
        parse_args([])


def test_require_gemini_api_key_exits_when_missing() -> None:
    # Patch out load_dotenv so this test's assertion doesn't depend on whether
    # a real .env file happens to exist on disk with a real GEMINI_API_KEY in it.
    with patch("client.agent.load_dotenv"), patch.dict(os.environ, {}, clear=True):
        with pytest.raises(SystemExit):
            require_gemini_api_key()


def test_require_gemini_api_key_returns_value_when_present() -> None:
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-123"}):
        assert require_gemini_api_key() == "test-key-123"


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
