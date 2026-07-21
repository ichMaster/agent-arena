"""Agent CLI scaffolding tests (ARENA-OPUS-OPUS-022). No LLM, no paid call.

join_match runs against the REAL app over httpx's in-process ASGI transport (no network).
"""

from pathlib import Path

import httpx
import pytest

from agent.agent import join_match, load_environment, parse_args
from server.database import create_engine, create_session_maker
from server.main import create_app


def test_parse_args_defaults() -> None:
    args = parse_args(["--match-id", "m1", "--profile", "profiles/aggressive.yml"])
    assert args.match_id == "m1"
    assert args.server_url == "http://127.0.0.1:8000"
    assert args.player_name is None


def test_parse_args_requires_match_and_profile() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--match-id", "m1"])  # missing --profile


def test_load_environment_reads_key_from_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=sk-from-dotenv\n", encoding="utf-8")
    assert load_environment(env_file) == "sk-from-dotenv"


def test_load_environment_missing_key_aborts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    empty = tmp_path / ".env"
    empty.write_text("# nothing here\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        load_environment(empty)


async def test_join_match_against_the_real_app(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/join.db")
    app = create_app(db_engine=engine, session_maker=create_session_maker(engine))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # init_models runs in lifespan; drive it via a startup request path -> use the transport's
        # lifespan by creating a match (create_app's lifespan runs on first ASGI lifespan event).
        # httpx ASGITransport doesn't run lifespan, so create the schema directly:
        from server.database import init_models

        await init_models(engine)
        match_id = (await client.post("/api/v1/lobby/match")).json()["match_id"]
        token = await join_match("http://test", match_id, "Ironclaw", client=client)
        assert len(token) > 0

        with pytest.raises(RuntimeError, match="not found"):
            await join_match("http://test", "no-such-match", "Ironclaw", client=client)
    await engine.dispose()
