#!/usr/bin/env bash
# Orchestrates a zero-human Tic-Tac-Toe match: creates a match on the running
# Game Server, then launches two Agent CLI instances (aggressive vs cowardly)
# against each other, streaming both logs to the terminal.
set -euo pipefail

SERVER_URL="${SERVER_URL:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "Creating a new match on ${SERVER_URL}..."
MATCH_JSON=$(curl -sf -X POST "${SERVER_URL}/api/v1/lobby/match") || {
    echo "ERROR: could not reach the server at ${SERVER_URL}. Is it running (uvicorn server.main:app)?" >&2
    exit 1
}

MATCH_ID=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['match_id'])" "${MATCH_JSON}")
if [ -z "${MATCH_ID}" ]; then
    echo "ERROR: server response did not contain a match_id: ${MATCH_JSON}" >&2
    exit 1
fi

echo ""
echo "Match created: ${MATCH_ID}"
echo "Spectate at:   ${SERVER_URL}/ui  (click 'Join Match' and paste the Match ID above)"
echo ""
read -r -p "Open the Web UI now, then press Enter to unleash the agents..." _unused

LOG_DIR=$(mktemp -d)
AGGRESSIVE_LOG="${LOG_DIR}/aggressive.log"
COWARDLY_LOG="${LOG_DIR}/cowardly.log"

echo "Starting Aggressor-Prime as X..."
(
    cd "${PROJECT_ROOT}"
    python3 client/agent.py --match-id "${MATCH_ID}" --symbol X --profile profiles/aggressive_bot.yml \
        --server-url "${SERVER_URL}"
) >"${AGGRESSIVE_LOG}" 2>&1 &
AGGRESSIVE_PID=$!

# The server assigns X/O purely by WebSocket connection order, not by
# --symbol — launching both agents concurrently would race for who actually
# connects first, silently flipping which persona plays which side. Wait for
# Aggressor-Prime's own "Joined as" confirmation in its log before starting
# the second agent, so the connection order (and therefore X/O) is
# deterministic rather than a race.
echo "Waiting for Aggressor-Prime to connect before starting the second agent..."
CONNECT_TIMEOUT_TICKS=50 # 50 * 0.2s = 10s
for _ in $(seq 1 "${CONNECT_TIMEOUT_TICKS}"); do
    if grep -q "Joined as" "${AGGRESSIVE_LOG}" 2>/dev/null; then
        break
    fi
    if ! kill -0 "${AGGRESSIVE_PID}" 2>/dev/null; then
        echo "ERROR: Aggressor-Prime exited before connecting — check ${AGGRESSIVE_LOG}" >&2
        cat "${AGGRESSIVE_LOG}" >&2
        exit 1
    fi
    sleep 0.2
done
if ! grep -q "Joined as" "${AGGRESSIVE_LOG}" 2>/dev/null; then
    echo "ERROR: Aggressor-Prime did not connect within ${CONNECT_TIMEOUT_TICKS} attempts — check ${AGGRESSIVE_LOG}" >&2
    exit 1
fi

echo "Starting Nervous-Nelly as O..."
(
    cd "${PROJECT_ROOT}"
    python3 client/agent.py --match-id "${MATCH_ID}" --symbol O --profile profiles/cowardly_bot.yml \
        --server-url "${SERVER_URL}"
) >"${COWARDLY_LOG}" 2>&1 &
COWARDLY_PID=$!

cleanup() {
    kill "${AGGRESSIVE_PID}" "${COWARDLY_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo ""
echo "Both agents launched (PIDs: ${AGGRESSIVE_PID}, ${COWARDLY_PID}). Tailing logs — Ctrl+C to stop."
echo ""

tail -n +1 -f "${AGGRESSIVE_LOG}" "${COWARDLY_LOG}"
