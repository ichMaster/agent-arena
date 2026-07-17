# AgentArena Specification

## 1. Overview
A modular, turn-based multiplayer game framework where human users and AI agents (powered by different LLMs) can play against each other. The architecture is designed to be game-agnostic, allowing any 2-player turn-based board game to be plugged into the system as a separate module.

## 2. Architecture & Core Components

### 2.1 Game Modules
The system uses an abstract **Game Interface** that standardizes how games are played. Any new game must implement this interface:
- `get_state()`: Returns a textual or structured representation of the current board.
- `get_valid_moves()`: Returns a list of legal moves for the current player.
- `apply_move(move)`: Updates the board state.
- `is_game_over()`: Returns the result (Win/Loss/Draw) if the game has ended.

**Initial Implementation**: Tic-Tac-Toe.
**Future Implementations**: Russian Checkers, Chess, Connect 4, etc.

### 2.2 Orchestration
- **Session Manager**: The core loop orchestrator. It manages turn order, tracks which entity (User or Agent) is currently playing, asks the specific game module for valid moves, and routes requests to the correct player.
- **Agent Interface**: A standardized wrapper for LLM APIs. It translates the current `get_state()` and `get_valid_moves()` into a prompt, calls the LLM, and parses the response into a valid game move.
- **User Interface**: The frontend for the human player to view the board, see agent actions, and input their own moves.

## 3. Agent Configuration
Each AI agent in a game session will be configured with:
- **Model**: The specific LLM to use (e.g., Gemini 3.1 Pro, GPT-4, Claude).
- **Persona/System Prompt**: Instructions detailing how the agent should behave, its skill level, and how it should format its move.
- **Memory**: (Optional) A short-term history of the current game's previous moves or chat messages.

## 4. Open Questions for Next Steps
1. **Platform**: Do you envision this as a Command Line Interface (CLI) app, a Web App, or something else? (This will determine how we build the "User Interface").
2. **Social Interaction**: Should the agents be able to "chat" or taunt each other and the user between turns, or just strictly output their moves?
3. **Agent Setup**: Do you want to pre-configure the agents, or should the user be able to dynamically pick which models play before starting a match?
