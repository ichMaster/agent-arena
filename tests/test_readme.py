"""Doc-smoke: keep the README honest (ARENA-OPUS-037). No commands are executed — no paid calls."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "token",
    [
        "uvicorn server.main:app",          # start the server
        "/ui",                              # the Web UI mount
        "agent/agent.py",                   # the agent CLI
        "--profile profiles/aggressive.yml",  # a real persona
        "scripts/run_arena.sh",             # the agent-vs-agent script
        "ANTHROPIC_API_KEY",                # the one required secret
        "pytest",                           # testing
        "/api/v1/lobby/join",               # the token source
        "arena.db",                         # data/reset
    ],
)
def test_readme_references_real_commands(token: str) -> None:
    assert token in README, f"README should document {token!r}"


def test_readme_shows_how_to_open_the_web_ui() -> None:
    # A newcomer must find the browsable UI URL up front, not buried in a mode.
    assert "http://127.0.0.1:8000/ui" in README


def test_readme_documents_all_three_run_modes() -> None:
    lowered = README.lower()
    assert "human vs agent" in lowered
    assert "agent vs agent" in lowered
    assert "observe" in lowered


def test_readme_has_no_stale_vendor_names() -> None:
    # This branch is Anthropic Haiku behind the LLMClient seam — the stub's Gemini/GPT-4 wording is gone.
    assert "GPT-4" not in README
    assert "Gemini" not in README
    assert "Haiku" in README


@pytest.mark.parametrize(
    "path",
    [
        "agent/agent.py",
        "scripts/run_arena.sh",
        "scripts/play.py",
        "profiles/aggressive.yml",
        "profiles/cautious.yml",
        ".env.example",
        "server/main.py",
    ],
)
def test_referenced_files_exist(path: str) -> None:
    assert (ROOT / path).is_file(), f"README/setup references {path}, which must exist"


def test_env_example_has_key_placeholder() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=" in env_example
