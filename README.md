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
