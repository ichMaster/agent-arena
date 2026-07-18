#!/bin/bash

# Exit on error
set -e

# Handle cleanup of background jobs on exit
trap cleanup EXIT

cleanup() {
    echo ""
    echo "[*] Cleaning up background processes..."
    if [ -n "$PID_X" ]; then
        kill "$PID_X" 2>/dev/null || true
    fi
    if [ -n "$PID_O" ]; then
        kill "$PID_O" 2>/dev/null || true
    fi
}

echo "[*] Creating new match on server..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/lobby/match)

# Parse match_id from JSON response
MATCH_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('match_id', ''))")

if [ -z "$MATCH_ID" ]; then
    echo "[-] Error: Failed to create match. Response was: $RESPONSE"
    exit 1
fi

echo "[+] Created Match ID: $MATCH_ID"
echo "[*] Open spectator Web UI at: http://localhost:8000/"
echo "[*] Click 'Join Match' and enter Match UUID: $MATCH_ID"
echo "[*] Waiting 5 seconds for spectator to connect before starting AI agents..."
sleep 5

echo "[*] Launching AggressiveBot as symbol X..."
.venv/bin/python client/agent.py --match-id "$MATCH_ID" --symbol X --profile profiles/aggressive_bot.yml &
PID_X=$!

# Wait briefly to guarantee X connects first and gets assigned 'X' symbol on the server
sleep 1.5

echo "[*] Launching CowardlyBot as symbol O..."
.venv/bin/python client/agent.py --match-id "$MATCH_ID" --symbol O --profile profiles/cowardly_bot.yml &
PID_O=$!

echo "[+] Both agents started. Monitoring match execution..."

# Wait for both processes to complete
wait "$PID_X" "$PID_O"
echo "[+] Match finished successfully."
