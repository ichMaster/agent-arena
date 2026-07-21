"""Static checks for scripts/run_arena.sh (ARENA-OPUS-OPUS-033, v04 gate).

The script launches real agent processes and makes real (paid) model calls when run -- so this test
never executes it. It asserts only on the source: valid bash, right references, and the
wait-for-agent-1 ordering that makes seat assignment deterministic. No server, no paid call.
"""

import stat
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run_arena.sh"


def test_script_exists_and_is_executable() -> None:
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & stat.S_IXUSR


def test_script_is_valid_bash() -> None:
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_references_profiles_endpoint_and_agent() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "profiles/aggressive.yml" in text
    assert "profiles/cautious.yml" in text
    assert "/api/v1/lobby/match" in text
    assert "agent/agent.py" in text


def test_waits_for_agent_one_before_agent_two() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.index("joined as") < text.index("launching agent 2")


def test_tells_human_to_observe_not_join() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "Observe" in text
    assert "NOT Join" in text or "not Join" in text


def test_has_cleanup_trap_and_strict_mode() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "trap cleanup" in text
    assert "INT" in text and "TERM" in text and "EXIT" in text
    assert "set -euo pipefail" in text
