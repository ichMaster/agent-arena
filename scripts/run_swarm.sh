#!/bin/bash

# Ensure backend is running
# This script assumes the server is available at localhost:8000

echo "[*] Creating Match..."
MATCH_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/lobby/match \
     -H "Content-Type: application/json" \
     -d '{"match_settings": {"game_type": "tictactoe"}}')

MATCH_ID=$(echo $MATCH_RESPONSE | grep -o '"match_id":"[^"]*' | cut -d'"' -f4)

if [ -z "$MATCH_ID" ]; then
    echo "[!] Failed to create match. Is the server running?"
    echo "Response: $MATCH_RESPONSE"
    exit 1
fi

echo "[*] Match created successfully: $MATCH_ID"
echo ""
echo "====================================================="
echo " OPEN WEB UI TO WATCH:"
echo " frontend/index.html (and manually enter Match ID)"
echo "====================================================="
echo ""
read -p "Press [Enter] when ready to spawn agents..."

# Activate virtual environment
source .venv/bin/activate
export PYTHONPATH=.

echo "[*] Spawning Player 1 (Aggressive)..."
python client/agent.py --match-id $MATCH_ID --profile profiles/aggressive_bot.yml &
P1=$!

sleep 2

echo "[*] Spawning Player 2 (Cowardly)..."
python client/agent.py --match-id $MATCH_ID --profile profiles/cowardly_bot.yml &
P2=$!

echo "[*] Agents spawned! Waiting for completion..."

# Wait for both background processes to finish
wait $P1
wait $P2

echo "[*] Swarm match completed."
