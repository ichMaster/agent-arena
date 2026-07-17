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
- [Game Architecture & Specification](game_specification.md)
