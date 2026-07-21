"""Regression for the run_arena "only one agent connects" bug: the agent must line-buffer its stdout
so the orchestrator sees `[agent] joined as ...` promptly even when stdout is a pipe/file, not a TTY.

Runs a subprocess that only imports agent.agent and exercises the buffering setup + a print — no
server, no LLM, no paid call.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_line_buffered_stdout_flushes_each_line_when_piped() -> None:
    # A long-running process (sleeps after printing) whose stdout is a PIPE. Without line-buffering,
    # the printed line would sit in the block buffer and readline() would block past the timeout.
    code = (
        "import time\n"
        "from agent.agent import _enable_line_buffered_stdout\n"
        "_enable_line_buffered_stdout()\n"
        "print('[agent] joined as X')\n"
        "time.sleep(30)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(REPO_ROOT),
        text=True,
    )
    try:
        assert proc.stdout is not None
        # If the line is flushed (line-buffered), this returns promptly; if block-buffered, it would
        # block until the process exits (30s) and the 5s wait would raise instead.
        line = _readline_with_timeout(proc, timeout=5.0)
        assert "joined as X" in line
    finally:
        proc.kill()
        proc.wait(timeout=5)


def _readline_with_timeout(proc: "subprocess.Popen[str]", timeout: float) -> str:
    """Read one line from proc.stdout, failing if nothing arrives within `timeout` seconds."""
    import threading

    result: list[str] = []

    def _read() -> None:
        assert proc.stdout is not None
        result.append(proc.stdout.readline())

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(timeout)
    assert not t.is_alive(), "no line flushed within the timeout -- stdout is block-buffered"
    return result[0]
