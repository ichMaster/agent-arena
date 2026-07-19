# AgentArena Specification

## 1. Overview
A modular, turn-based multiplayer game framework where human users and AI agents (powered by different LLMs) can play against each other. The architecture is designed to be game-agnostic, allowing any 2-player turn-based board game to be plugged into the system as a separate module.

## 2. Architecture & Core Components

The framework uses a decoupled **Client-Server** architecture to support various types of players and real-time monitoring.

### 2.1 Game Server (Central Authority)
- Manages active game sessions, stores the authoritative game state, and validates all moves.
- Exposes APIs (REST / WebSockets) for clients to connect, retrieve state, and submit moves.
- **Tech Stack**: Python and FastAPI.

### 2.2 Agent Client (CLI)
- A standalone Command Line application running the LLM logic (**Tech Stack**: Python).
- **Operator Chat**: A human can chat directly with the agent via the CLI to give it instructions or observe its reasoning.
- **Tool Use**: The agent uses specific commands/tools to interact with the Game Server (e.g., `connect_to_server`, `get_game_status`, `submit_move`).

### 2.3 User & Admin Web UI
- **Player View**: A web frontend for human users to connect to the server, view the board graphically, and play their turns.
- **Admin View**: A dashboard allowing administrators to observe all active games, monitor agent behaviors, and review past matches.

### 2.4 Game Modules
The system uses an abstract **Game Interface** that standardizes how games are played. Any new game must implement this interface on the server:
- `get_state()`: Returns a textual or structured representation of the current board.
- `get_valid_moves()`: Returns a list of legal moves for the current player.
- `apply_move(move)`: Updates the board state.
- `is_game_over()`: Returns the result (Win/Loss/Draw) if the game has ended.

**Initial Implementation**: Tic-Tac-Toe.
**Future Implementations**: Russian Checkers, Chess, Connect 4, etc.

### 2.5 Communication & Chat
- The platform includes a real-time chat system tied to each game session.
- Human users can chat via the Web UI.
- AI Agents can chat via the CLI (their messages are broadcast to the Web UI and other players). This allows agents to taunt, strategize aloud, or interact with humans and each other during the game.

### 2.6 Event-Driven Networking (WebSockets)
Instead of inefficient REST polling, the system uses an event-driven architecture via WebSockets for real-time interaction:
- **Connection**: Clients (Agents and Web UI) maintain a persistent WebSocket connection to the Game Server.
- **Trigger Events**: The server pushes JSON events (e.g., `your_turn`, `chat_message`) directly to the clients.
- **Agent Execution**: Upon receiving a `your_turn` event containing the board state and valid moves, the Agent CLI instantly formats a prompt, queries the LLM, and pushes a `submit_move` action back through the open WebSocket.

## 3. Agent Designer & Configuration
The platform will feature an **Agent Designer** component. Users will be able to design, configure, and "build" their own custom agents.
- **Output**: The designer will package the configuration into a standalone Python application (the Agent Client) that the user can run.
- **Configuration Parameters**:
  - **Model**: The specific LLM to use (Anthopic Haiku).
  - **Persona/System Prompt**: Instructions detailing how the agent should behave, its skill level, and its playstyle.
  - **Memory**: A short-term history length for the current game's previous moves or chat messages.

### 3.1 Agent Tools (Commands)
The built agent will be equipped with specific tools (functions) it can call to interact with the system. The LLM will autonomously decide when to use these based on the state of the game:
- `get_valid_moves()`: Ask the server for the list of legal moves for the current turn.
- `submit_move(move)`: Send a chosen move to the Game Server via WebSockets.
- `send_chat_message(message)`: Broadcast a chat or taunt to the room.
- `get_game_status()`: Manually request the current board state and score if the agent needs a refresher.
