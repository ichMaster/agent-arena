#!/usr/bin/env bash
#
# run_arena.sh — launch one agent-vs-agent match a human can watch (architecture.md §12, mode 2).
#
# Creates a match, starts two persona agents in order (agent 1 → X, agent 2 → O — deterministic,
# no seat race), prints the Observe link, and tails both agents' logs until Ctrl-C.
#
# Prereqs: the server is running (`.venv/bin/uvicorn server.main:app --port 8000`) and the agent's
# ANTHROPIC_API_KEY is in ./.env. This runs the REAL agents (live Haiku calls).
#
# Usage:  ./scripts/run_arena.sh [X_PROFILE] [O_PROFILE]
#   defaults: profiles/aggressive.yml (X)  vs  profiles/cautious.yml (O)
#   env:      SERVER_URL (default http://127.0.0.1:8000), PYTHON (default .venv/bin/python)

set -euo pipefail

# Run from the repo root so ./.env, profiles/, and agent/ resolve regardless of the caller's CWD.
cd "$(dirname "$0")/.."

SERVER_URL="${SERVER_URL:-http://127.0.0.1:8000}"
PROFILE_X="${1:-profiles/aggressive.yml}"
PROFILE_O="${2:-profiles/cautious.yml}"

PYTHON="${PYTHON:-.venv/bin/python}"
[ -x "$PYTHON" ] || PYTHON="python3"

# 1. Create a match and read its id (no jq dependency — parse the JSON with Python).
MATCH_JSON="$(curl -sf -X POST "$SERVER_URL/api/v1/lobby/match")" || {
  echo "error: could not reach the server at $SERVER_URL — is uvicorn running?" >&2
  exit 1
}
MATCH_ID="$("$PYTHON" -c 'import sys, json; print(json.load(sys.stdin)["match_id"])' <<<"$MATCH_JSON")"

echo "=============================================================="
echo "  Match ID : $MATCH_ID"
echo "  Watch it : open  $SERVER_URL/ui  ->  Observe  ->  paste the Match ID"
echo "  IMPORTANT: use Observe, NOT Join — Join would steal a player seat."
echo "  X = $PROFILE_X    O = $PROFILE_O"
echo "  (Ctrl-C to stop both agents.)"
echo "=============================================================="

LOG_X="$(mktemp -t arena_x.XXXXXX)"
LOG_O="$(mktemp -t arena_o.XXXXXX)"
PID_X=""; PID_O=""

cleanup() {
  # Always stop both agents and drop the temp logs on exit / Ctrl-C.
  [ -n "$PID_X" ] && kill "$PID_X" 2>/dev/null || true
  [ -n "$PID_O" ] && kill "$PID_O" 2>/dev/null || true
  rm -f "$LOG_X" "$LOG_O" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

# 2. Launch agent 1 (X). Wait for its "joined as" line BEFORE starting agent 2 so the seats are
#    deterministic (first connect = X). Seat assignment is already race-safe server-side; this only
#    fixes which persona is X vs O.
"$PYTHON" agent/agent.py --match-id "$MATCH_ID" --profile "$PROFILE_X" --server-url "$SERVER_URL" \
  >"$LOG_X" 2>&1 &
PID_X=$!

echo "[arena] waiting for X ($PROFILE_X) to join…"
until grep -q "joined as" "$LOG_X" 2>/dev/null; do
  if ! kill -0 "$PID_X" 2>/dev/null; then
    echo "error: agent X exited before joining:" >&2
    cat "$LOG_X" >&2
    exit 1
  fi
  sleep 0.3
done

# 3. Launch agent 2 (O).
"$PYTHON" agent/agent.py --match-id "$MATCH_ID" --profile "$PROFILE_O" --server-url "$SERVER_URL" \
  >"$LOG_O" 2>&1 &
PID_O=$!

echo "[arena] both agents connected — streaming their play + banter (Ctrl-C to stop):"
echo

# 4. Stream both agents' logs until interrupted.
tail -f "$LOG_X" "$LOG_O"
