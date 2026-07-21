"""Doc-smoke test for README.md (ARENA-OPUS-OPUS-037, v05 gate). Never executes any live/paid command
-- only reads the README text and confirms the files/commands it references actually exist.
"""

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")


def test_readme_references_the_real_entry_points() -> None:
    for token in (
        "uvicorn server.main:app",
        "/ui",
        "agent/agent.py",
        "profiles/aggressive.yml",
        "profiles/cautious.yml",
        "scripts/run_arena.sh",
        "ANTHROPIC_API_KEY",
        "pytest",
    ):
        assert token in README, f"README is missing a reference to {token!r}"


def test_referenced_files_actually_exist() -> None:
    for rel in (
        "agent/agent.py",
        "scripts/run_arena.sh",
        "profiles/aggressive.yml",
        "profiles/cautious.yml",
        ".env.example",
    ):
        assert (REPO_ROOT / rel).is_file(), f"{rel} referenced but missing"


def test_all_three_run_modes_are_documented() -> None:
    assert "Human vs. agent" in README
    assert "Agent vs. agent" in README
    assert "Observe" in README
    assert "not Join" in README or "never Join" in README  # Observe != Join


def test_no_stale_vendor_names() -> None:
    for stale in ("Gemini", "GPT-4", "GPT-3"):
        assert stale not in README, f"README still names the stale vendor {stale!r}"


def test_env_example_tracked_not_gitignored() -> None:
    lines = [line.strip() for line in (REPO_ROOT / ".gitignore").read_text().splitlines()]
    assert ".env" in lines           # the real secret file IS ignored
    assert ".env.example" not in lines  # the template is NOT
    assert (REPO_ROOT / ".env.example").is_file()


def test_uvicorn_is_a_declared_dependency() -> None:
    """The README's first command is `uvicorn server.main:app` -- a clean install must provide it."""
    manifest = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    deps = manifest["project"]["dependencies"]
    assert any(d.startswith("uvicorn") for d in deps), "pyproject.toml must declare uvicorn"
