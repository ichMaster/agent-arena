#!/usr/bin/env bash
set -e

SERVER_URL=${1:-"http://localhost:8000"}

echo "==========================================="
echo "        AGENT ARENA SWARM ORCHESTRATOR     "
echo "==========================================="

echo "[*] Creating a new match at $SERVER_URL..."
RESPONSE=$(curl -s -X POST "$SERVER_URL/api/v1/lobby/match")

if [[ -z "$RESPONSE" || "$RESPONSE" == *"Internal Server Error"* ]]; then
    echo "[-] Failed to connect to server. Is it running?"
    exit 1
fi

MATCH_ID=$(echo $RESPONSE | grep -o '"match_id":"[^"]*' | cut -d'"' -f4)

if [ -z "$MATCH_ID" ]; then
    echo "[-] Failed to parse Match ID from response: $RESPONSE"
    exit 1
fi

echo "[+] Match created successfully!"
echo "    -> Match ID: $MATCH_ID"
echo ""
echo "==========================================="
echo " SPECTATOR INSTRUCTIONS:"
echo " 1. Press Enter below to launch the bots FIRST."
echo " 2. Once they start, open: $SERVER_URL/ui"
echo " 3. Click 'Join Match ID' and paste: $MATCH_ID"
echo "==========================================="
echo ""

read -p "Press Enter to release the Swarm (then join as a spectator)..."

# Start Player X (Aggressive Bot)
echo "[*] Launching Player X (Aggressive Bot)..."
PYTHONPATH=. python client/agent.py \
    --match-id $MATCH_ID \
    --symbol X \
    --profile profiles/aggressive_bot.yml \
    --url $SERVER_URL &
P1_PID=$!

# Add a slight delay to ensure Player X joins first (since X goes first)
sleep 1

# Start Player O (Cowardly Bot)
echo "[*] Launching Player O (Cowardly Bot)..."
PYTHONPATH=. python client/agent.py \
    --match-id $MATCH_ID \
    --symbol O \
    --profile profiles/cowardly_bot.yml \
    --url $SERVER_URL &
P2_PID=$!

echo "[+] Swarm launched! (PIDs: X=$P1_PID, O=$P2_PID)"
echo "[*] Streaming logs below. Press Ctrl+C to terminate both agents."

# Setup cleanup trap
trap "echo '[-] Shutting down swarm...'; kill -9 $P1_PID $P2_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# Wait for both background processes
wait $P1_PID
wait $P2_PID

echo "[+] Swarm completed."
