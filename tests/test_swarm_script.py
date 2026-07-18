import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_swarm.sh"


def test_swarm_script_exists_and_is_executable() -> None:
    assert SCRIPT_PATH.exists()
    assert os.access(SCRIPT_PATH, os.X_OK)


def test_swarm_script_has_valid_bash_syntax() -> None:
    result = subprocess.run(["bash", "-n", str(SCRIPT_PATH)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_swarm_script_references_existing_profiles() -> None:
    content = SCRIPT_PATH.read_text()
    assert "profiles/aggressive_bot.yml" in content
    assert "profiles/cowardly_bot.yml" in content
    assert (REPO_ROOT / "profiles" / "aggressive_bot.yml").exists()
    assert (REPO_ROOT / "profiles" / "cowardly_bot.yml").exists()


def test_swarm_script_targets_the_real_lobby_endpoint_and_symbols() -> None:
    content = SCRIPT_PATH.read_text()
    assert "/api/v1/lobby/match" in content
    assert "--symbol X" in content
    assert "--symbol O" in content
    assert "client/agent.py" in content


def test_swarm_script_waits_for_the_first_agent_before_starting_the_second() -> None:
    """Regression: launching both agents concurrently races for who actually
    connects first (the server assigns X/O by connection order, not by
    --symbol) — the script must block on Aggressor-Prime's own connection
    confirmation before starting Nervous-Nelly, and it must do so BEFORE the
    second agent's launch line appears in the file."""
    content = SCRIPT_PATH.read_text()
    assert "Joined as" in content  # the exact log line client/agent.py prints on connect

    wait_index = content.index('grep -q "Joined as"')
    aggressive_launch_index = content.index("--symbol X")
    cowardly_launch_index = content.index("--symbol O")
    assert aggressive_launch_index < wait_index < cowardly_launch_index
