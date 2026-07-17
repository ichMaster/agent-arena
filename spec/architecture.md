# Architecture — Agent Arena

## Overview
A modular, turn-based multiplayer framework where human players and AI agents (powered by LLMs) can compete. The architecture strictly separates the **Game Server** (central authority and state) from the **Clients** (Agent CLI and Web UI). All communication is asynchronous via WebSockets, ensuring real-time, event-driven gameplay without polling.

---

## 1. Game Server Components
- **FastAPI Core:** The central authority handling concurrent WebSocket connections asynchronously. 
- **Game Modules (Core Logic):** Independent packages implementing a strict `GameInterface` (`get_state`, `get_valid_moves`, `apply_move`, `is_game_over`). The Server holds an active instance of a module (like Tic-Tac-Toe) for every live match.
- **Connection Manager:** A singleton tracking active matches. It maps `match_id` to a list of connected `WebSocket` clients and handles targeted messaging and broadcasts.

---

## 2. Agent Architecture
The Agent Client operates completely autonomously, separated from the Server. It runs as a persistent Python process.
- **Event Loop:** The agent listens asynchronously for WebSocket push events. It remains dormant until it receives a `your_turn` payload.
- **Context Assembly:** Upon receiving its turn, the agent builds a prompt combining:
  1. **System Persona:** Who the agent is and how it behaves.
  2. **Memory Window:** The last N turns and chat messages to maintain temporal continuity.
  3. **Current State:** The current board state and valid legal moves.
- **LLM Abstraction Seam (`LLMClient`):** A strict interface boundary separating the agent from specific vendor SDKs. It allows instant swapping between `GoogleGeminiClient`, `AnthropicClaudeClient`, etc., via config.
- **Tool Calling Engine:** The LLM does not just generate text; it is forced to use native Tool Calling (or strict JSON schema parsing) to execute actions. It extracts `submit_move(cell)` and `send_chat_message(text)` and transmits them as JSON payloads back to the Server.

---

## 3. Agent Designer Architecture
The Designer is a configuration and scaffolding layer used to build unique Agent identities without touching the core Python logic.
- **Agent Profiles (JSON/YAML):** A standardized schema defining an Agent's traits: `name`, `model_provider`, `temperature`, `system_prompt` (playstyle/tone), and `memory_limit`.
- **Generator Engine:** A script that parses an Agent Profile and spawns an instance of the Agent Client injected with those exact parameters.
- **Swarm Support:** The architecture supports running multiple Agent Clients simultaneously from different profiles, allowing "Aggressive AI" to battle "Defensive AI" in the same server match.

---

## 4. Storage & Persistence
To ensure active games are not lost during a restart, the system uses a durable Repository layer.
- **Database Engine:** SQLite (via an ORM like SQLAlchemy) for lightweight, single-node persistence, easily upgradable to PostgreSQL for production.
- **Data Models:**
  - `Matches`: Tracks `match_id`, the active game module, current board state JSON, and status (active/finished).
  - `MoveLog`: A ledger of every action taken in a match for replayability.
  - `ChatLog`: Historical chat records for the room.
- **Stateless Server Recovery:** Every applied move is checkpointed. If the server crashes, it rehydrates the active matches from the database into RAM upon boot.

---

## 5. Security & Isolation
- **Authentication:** Clients must obtain a session token via an HTTP Lobby endpoint before upgrading to a WebSocket connection. Agents are issued secure bot-tokens.
- **Role-Based Execution:** The server strictly tracks the `user_id` mapped to Player X and Player O. A client cannot submit a move for a slot they do not own.
- **Strict Input Validation:** All incoming WebSocket JSON payloads are validated through Pydantic models. 
- **The Ultimate Authority:** The LLM's outputs are considered entirely untrusted. The Server's `GameInterface` provides the final, unbreachable mathematical barrier against illegal moves.
- **Secret Isolation:** API keys for the LLMs (e.g., `OPENAI_API_KEY`) live securely within the Agent's `.env` space and are never transmitted to the Server or Web UI.

---

## 6. Testing Strategy
- **Unit Testing:** Fast, deterministic tests for game logic, invalid move rejection, and win/loss condition calculations. 
- **Mocked LLMs:** The `LLMClient` seam is heavily mocked during CI. Tests simulate LLM tool calls without ever hitting paid external APIs, ensuring tests run instantly and cost nothing.
- **Contract Testing:** Validates that the schema for WebSockets (e.g., `your_turn` events) and the `GameInterface` remain stable and unbroken.
- **Integration Testing:** Spin up a temporary server, a mock UI client, and a mocked Agent Client to simulate end-to-end matches natively.

---

## 7. Deployment & Infrastructure
- **Containerization:** The repository will include separate `Dockerfile`s for the Server, the Agent Runner, and the Web UI.
- **Local Orchestration:** A `docker-compose.yml` file allows a developer to spin up the database, server, UI, and two Agents with a single `docker-compose up` command.
- **Cloud Hosting:** 
  - *Game Server:* Deployed to a persistent PaaS (like Google Cloud Run, Render, or Railway) to maintain WebSocket connections.
  - *Web UI:* Hosted via static CDN delivery (like Vercel or Firebase Hosting).
  - *Agents:* Can be run anywhere—locally on a user's machine, or as persistent background workers in the cloud.

---

## 8. Project Structure & Modules
The repository is organized into distinct, isolated directory domains to prevent tight coupling.

```text
agent-arena/
├── server/                 # The Game Server (FastAPI)
│   ├── main.py             # FastAPI application and route definitions
│   ├── connection.py       # WebSocket ConnectionManager singleton
│   ├── database.py         # SQLAlchemy DB connection and session maker
│   ├── models.py           # Database schemas (Matches, MoveLog, ChatLog)
│   ├── schemas.py          # Pydantic validation models for I/O payloads
│   └── games/              # Swappable Game Modules
│       ├── __init__.py
│       ├── interface.py    # The abstract GameInterface base class
│       └── tictactoe.py    # Concrete Tic-Tac-Toe implementation
│
├── agent/                  # The Agent Client CLI
│   ├── client.py           # WebSocket client and async event loop
│   ├── parser.py           # Extracts tool calls from raw LLM text
│   └── llm/                # LLM Abstraction Seam
│       ├── __init__.py
│       ├── interface.py    # Abstract LLMClient definition
│       └── gemini.py       # Concrete Google Gemini implementation
│
├── designer/               # The Agent Designer
│   ├── builder.py          # Script to generate an agent from a config
│   ├── schemas.py          # Pydantic models for Agent Profiles
│   └── profiles/           # Saved YAML/JSON configurations
│       ├── aggressive.yml
│       └── defensive.yml
│
├── web/                    # The Web UI (Vanilla HTML/JS/CSS)
│   ├── index.html          # Main application structure
│   ├── styles.css          # UI styling and animations
│   └── app.js              # WebSocket logic, DOM updates, and chat
│
├── tests/                  # Unified testing suite
│   ├── server/             # FastAPI, Websocket, and Game logic tests
│   ├── agent/              # Agent parsing and mocked LLM tests
│   └── e2e/                # Integration tests (Server + Agent + Mock Web)
│
├── docker-compose.yml      # Local container orchestration
└── .env                    # Secret isolation (ignored by Git)
```
