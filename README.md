# AgentArena

A modular, turn-based multiplayer game framework designed to let human users and AI agents (powered by various Large Language Models like Gemini, GPT-4, Claude, etc.) play against each other in the same session.

## Features
- **Modular Game Architecture**: Designed around an abstract Game Interface (`get_state`, `get_valid_moves`, `apply_move`), making it easy to plug in any 2-player turn-based board game.
- **LLM Agent Wrappers**: Standardized interfaces to connect different LLM APIs, complete with system prompts and persona configurations.
- **Multiplayer Orchestration**: A Session Manager that handles turn order, routes game states to the correct player/agent, and parses their responses.

## Current Games
- **Tic-Tac-Toe** (Initial implementation)
- *More coming soon (Russian Checkers, Connect 4, etc.)*

## Documentation
- [Roadmap](spec/roadmap.md)
- [System Architecture](spec/architecture.md)
- [Game Specification](spec/game_specification.md)
- [Web UI Specification](spec/web_ui_specification.md)

## Getting Started

1. Set up a virtual environment and install the dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the Game Server:
```bash
uvicorn server.main:app --reload
```

## Testing the API

You can test the server by navigating to the interactive Swagger UI documentation at **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**. 

Alternatively, you can use `curl` from the terminal:

**Health Check:**
```bash
curl http://127.0.0.1:8000/api/v1/health
```

**Generate a Match:**
```bash
curl -X POST http://127.0.0.1:8000/api/v1/lobby/match
```
*(Copy the `match_id` from the response)*

**Join the Match:**
```bash
curl -X POST http://127.0.0.1:8000/api/v1/lobby/join \
  -H "Content-Type: application/json" \
  -d '{"match_id": "<PASTE-YOUR-MATCH-ID-HERE>", "player_name": "Player 1"}'
```

## Testing WebSockets (Tic-Tac-Toe)

You can manually test the real-time WebSocket capabilities and play a full game of Tic-Tac-Toe using the modern Web UI:

1. Ensure your database is initialized:
```bash
PYTHONPATH=. python server/init_db.py
```

2. Start the game server:
```bash
PYTHONPATH=. uvicorn server.main:app --reload
```

3. Open **[http://localhost:8000/ui](http://localhost:8000/ui)** in your browser.
4. Click **"Host New Match"** in the browser. You'll see it connect and the board will activate. You are player **X**.
5. To test multiplayer, open a *second tab* in your browser and go to `http://localhost:8000/ui`. 
6. In the second tab, click **"Join Match ID..."** and paste the Match ID from the first tab. You'll join as player **O**.
7. Play the game! The server will enforce turns, broadcast the board state, and declare a winner when the game is over.

## Testing the Agent CLI 

The Agent CLI connects to the game, listens to events, and uses Gemini to autonomously evaluate the board, make moves, and trash-talk its opponents in real-time.

1. Ensure your `.env` file has a valid `GEMINI_API_KEY`.
2. Start the game server:
   ```bash
   PYTHONPATH=. uvicorn server.main:app --reload
   ```
3. Open `http://localhost:8000/ui` in your web browser.
4. Click **Host New Match**. You will be assigned the symbol `X`.
5. Copy the **Match ID** from the UI.
6. Open a new terminal instance and run the Agent CLI, passing it the Match ID, the symbol `O`, and a profile configuration:
   ```bash
   PYTHONPATH=. python client/agent.py --match-id <YOUR_MATCH_ID> --symbol O --profile profiles/aggressive_bot.yml
   ```
7. Go back to your browser and click on the Tic-Tac-Toe board to make your first move as `X`.
8. Check the Agent's terminal! It will detect that it is now `O`'s turn, construct the prompt, query Gemini, and **automatically submit its move** back to the server. You will see its move appear on your browser board, along with its comment in the chat log!

*Note: You can also run two agents against each other by pointing them both to the same Match ID, one as X and one as O.*
