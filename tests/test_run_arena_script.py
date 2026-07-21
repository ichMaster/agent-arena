"""Static checks for scripts/run_arena.sh (ARENA-OPUS-033). The script is NOT executed — that needs a
live server + paid Haiku calls; we assert its shape only. No LLM, no paid call, no server started."""

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run_arena.sh"


@pytest.fixture(scope="module")
def script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_script_exists_and_is_executable() -> None:
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & 0o111, "run_arena.sh must be executable"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_script_is_valid_bash() -> None:
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_references_both_profiles_and_lobby(script_text: str) -> None:
    assert "profiles/aggressive.yml" in script_text
    assert "profiles/cautious.yml" in script_text
    assert "/api/v1/lobby/match" in script_text
    assert "agent/agent.py" in script_text


def test_waits_for_first_agent_before_second(script_text: str) -> None:
    # Order matters: the wait-for-join loop must appear before the second agent launch.
    wait_idx = script_text.index('grep -q "joined as"')
    o_launch_idx = script_text.index('--profile "$PROFILE_O"')
    assert wait_idx < o_launch_idx, "must wait for agent X's join before launching agent O"


def test_instructs_observe_not_join(script_text: str) -> None:
    assert "Observe" in script_text
    # Explicitly steers the human away from Join (which would claim a player seat).
    assert "Join" in script_text and "NOT Join" in script_text


def test_cleans_up_on_exit(script_text: str) -> None:
    assert "trap cleanup" in script_text
    assert "set -euo pipefail" in script_text
