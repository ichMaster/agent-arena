# Agent Arena: Solution Architecture

## Overview
Agent Arena is a platform designed to pit Large Language Model (LLM) agents against each other in turn-based games (currently Tic-Tac-Toe). The system supports a mix of human and AI players and features a robust real-time synchronization engine powered by WebSockets.

The architecture is split into three main layers:
1. **FastAPI Backend (Server)**: Manages game logic, lobbys, WebSocket connections, and state broadcasting.
2. **Python Client (Agents)**: Autonomous clients powered by Gemini that connect to the backend, perceive the game state, and generate strategic moves based on YAML persona profiles.
3. **Vanilla JS Web UI**: A spectator and human-player interface that visualizes the game board in real time and streams chat logs.

---

## High-Level Architecture Diagram

```mermaid
graph TD
    subgraph Frontend
        W[Web UI spectator/player]
    end

    subgraph Backend Server
        F[FastAPI App]
        L[Lobby HTTP API]
        WS[WebSocket Manager]
        G[Game Engine: TicTacToe]
        
        F --> L
        F --> WS
        WS --> G
    end

    subgraph Agent Swarm
        A1[Agent Client: Aggressive]
        A2[Agent Client: Cowardly]
        P[YAML Profiles]
        LLM[Google GenAI API]
        
        A1 -.-> P
        A2 -.-> P
        A1 --> LLM
        A2 --> LLM
    end

    W -- HTTP POST /join --> L
    W -- WS /ws/match --> WS
    
    A1 -- WS /ws/match --> WS
    A2 -- WS /ws/match --> WS
```

---

## Component Deep Dive

### 1. Server (`server/`)
- **`main.py`**: The FastAPI entry point. It serves the static files for the Web UI and provides the HTTP endpoints for creating (`/api/v1/lobby/match`) and joining (`/api/v1/lobby/join`) matches.
- **`websockets.py`**: A stateful Connection Manager that handles active WebSocket sessions. It routes `submit_move` events to the game engine and broadcasts `state_update` and `chat_message` events to all connected clients in a match.
- **`games/tictactoe.py`**: The core logic engine. It maintains the 3x3 grid, validates moves, checks for win/draw conditions, and serializes the state to JSON.

### 2. Client Agents (`client/`)
- **`agent.py`**: The primary event loop for an autonomous agent. It connects to the server via WebSockets, listens for `state_update` events, and triggers a response when it is the agent's turn.
- **`llm.py`**: The integration layer with Google's `genai` SDK. It injects the game state into a prompt and enforces structured JSON output using `response_schema` so the agent always returns a valid move index and a chat comment.
- **`profile.py`**: Loads the agent's persona from a `.yml` file (e.g., `profiles/aggressive_bot.yml`), injecting behavioral instructions (like "you are a cowardly bot") into the LLM system prompt.

### 3. Web Interface (`web/`)
- Built with vanilla HTML/CSS/JS. It connects to the same `/ws/match/{match_id}` endpoint as the bots.
- Automatically handles reconnection gracefully.
- Parses incoming JSON payloads to update the DOM (updating the CSS classes on the Tic-Tac-Toe grid and appending to the chat log).

### 4. Swarm Orchestration (`scripts/run_swarm.sh`)
- A Bash script that automates match creation via `curl`.
- Extracts the generated Match ID and forks two `agent.py` background processes.
- Assigns different YAML profiles to the bots, effectively creating a zero-human game that spectators can watch via the Web UI.
