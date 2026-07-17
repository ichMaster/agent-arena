# Roadmap — Agent Arena

Five distinct phases, built sequentially: **Phase 1** (Game Server backbone) → **Phase 2** (Tic-Tac-Toe game logic) → **Phase 3** (Initial hardcoded Agent) → **Phase 4** (Web UI) → **Phase 5** (Agent Designer & Dynamic Agents).

## Versioning Strategy
The project uses strict Semantic Versioning tied to our implementation phases, formatted as **`vXX.YY.ZZ`**:
- **`XX` (Phase):** The current roadmap phase number (e.g., `01` for Phase 1).
- **`YY` (Version):** The feature iteration within the phase (e.g., `01.01.00`).
- **`ZZ` (Fixes):** Patch increments for bugfixes after a feature is implemented (e.g., `01.01.01`).

---

## Phase 1 — Game Server Foundation
**Goal:** Establish the asynchronous networking backbone, database persistence, and lobby system.

### v01.01.00 — Server Skeleton & Lobby
**Goal:** Set up the fundamental API application and the HTTP routing for players to discover and join matches.
- **Detailed Tasks:**
  - Create `requirements.txt` locking versions for `fastapi`, `uvicorn`, `pydantic`, `websockets`, and `sqlalchemy`.
  - Initialize the FastAPI app instance with CORS middleware allowing all origins (for local development).
  - Implement `/api/v1/health` endpoint for liveness probes.
  - Implement `/api/v1/lobby/match` HTTP POST endpoint. It generates a unique `match_id` (UUID4) and returns it.
  - Implement `/api/v1/lobby/join` HTTP POST endpoint. It accepts a `match_id` and `player_name` and returns a temporary opaque Auth Token used for WebSocket authentication.
- **DoD:** HTTP endpoints return `200 OK` with valid JSON containing UUIDs and tokens.
- **Tests:** Pytest unit tests for REST endpoints validating JSON responses. *(Ref: [architecture.md](architecture.md) §1)*

### v01.02.00 — Database Layer
**Goal:** Implement the persistence layer so matches can survive server restarts.
- **Detailed Tasks:**
  - Configure SQLAlchemy with an asynchronous SQLite engine (`sqlite+aiosqlite:///arena.db`).
  - Define `MatchModel`: `id` (PK, string UUID), `status` (Enum: PENDING, ACTIVE, COMPLETED), `created_at` (Datetime).
  - Define `MoveLogModel`: `id` (PK), `match_id` (FK), `player_id` (String), `move_payload` (JSON), `timestamp`.
  - Define `ChatLogModel`: `id` (PK), `match_id` (FK), `sender` (String), `message` (Text), `timestamp`.
  - Implement a `Repository` class abstracting CRUD operations away from the WebSocket logic.
- **DoD:** A script can successfully instantiate the database schema and insert/query dummy records for matches and chat logs.
- **Tests:** Database unit tests verifying schema creation, foreign key constraints, and CRUD methods. *(Ref: [architecture.md](architecture.md) §4)*

### v01.03.00 — WebSocket Connection Manager
**Goal:** Enable real-time, event-driven, bidirectional communication.
- **Detailed Tasks:**
  - Build the `ConnectionManager` singleton class mapping `match_id` -> `List[WebSocket]`.
  - Implement the `/ws/match/{match_id}` endpoint. It must extract the Auth Token from query parameters and validate it before `await websocket.accept()`.
  - Create Pydantic schemas for inbound payloads (`ClientActionPayload`) and outbound events (`ServerPushEvent`).
  - Implement a loop that awaits `websocket.receive_json()`, validates it via Pydantic, and routes it to the chat broadcast or move validator.
- **DoD:** Multiple dummy clients can connect to the same `match_id` and exchange chat JSON payloads without the server crashing.
- **Tests:** Pytest-asyncio tests simulating concurrent WebSocket connections broadcasting payloads.

---

## Phase 2 — Game Logic (Tic-Tac-Toe)
**Goal:** Implement the rules engine, state tracking, and interface.

### v02.01.00 — Game Interface
**Goal:** Define the strict interface all future game modules must follow.
- **Detailed Tasks:**
  - Create `games/interface.py` using Python's `abc` module.
  - Define `@abstractmethod get_state() -> dict`.
  - Define `@abstractmethod get_valid_moves() -> list`.
  - Define `@abstractmethod apply_move(player: str, move: Any) -> bool`.
  - Define `@abstractmethod is_game_over() -> Optional[str]`.
- **DoD:** The `GameInterface` is completely decoupled from WebSockets or HTTP logic. *(Ref: [game_specification.md](game_specification.md) §2.4)*
- **Tests:** Linter/MyPy typing checks to ensure abstract definitions are enforced.

### v02.02.00 — Tic-Tac-Toe Engine
**Goal:** Build the concrete logic for a 3x3 grid game.
- **Detailed Tasks:**
  - Create `games/tictactoe.py` implementing `GameInterface`.
  - Store the board state internally as a 9-element 1D array or 3x3 2D array.
  - Implement `apply_move` to check if a cell is empty before marking 'X' or 'O'.
  - Implement `is_game_over` using a mathematical check for 8 possible winning lines (3 horizontal, 3 vertical, 2 diagonal) or a draw (full board).
- **DoD:** The engine correctly tracks the board state and identifies a winner or draw without external server context.
- **Tests:** Highly exhaustive unit tests for every winning permutation, draw states, and out-of-bounds move rejections.

### v02.03.00 — Server Integration
**Goal:** Bind the Game Logic to the active WebSocket session.
- **Detailed Tasks:**
  - When a match becomes `ACTIVE`, the server instantiates a `TicTacToe` class in memory.
  - Intercept incoming `submit_move` JSON payloads and route the move to `game.apply_move()`.
  - If valid: Persist the move to the `MoveLog` DB table, then broadcast a `move_made` event to all clients.
  - Following the move, broadcast a `your_turn` event exclusively to the opponent containing `get_valid_moves()`.
- **DoD:** The server successfully enforces the rules over the WebSocket network layer.
- **Tests:** Integration tests verifying invalid WebSocket move payloads are rejected and do not corrupt the server state.

---

## Phase 3 — Initial Agent Client
**Goal:** Build a hardcoded AI agent capable of playing the game autonomously.

### v03.01.00 — Agent Skeleton
**Goal:** Build the standalone Agent Python script and networking layer.
- **Detailed Tasks:**
  - Create a CLI script initializing `asyncio` and `websockets` libraries.
  - Add an HTTP call to the Lobby to acquire a match Auth Token.
  - Build the asynchronous event loop: `async for message in websocket:`
  - Add JSON parsing to filter out `chat_message` events and trigger logic *only* when a `your_turn` event is received.
- **DoD:** The Agent CLI can connect to the server and cleanly log incoming network events to stdout. *(Ref: [architecture.md](architecture.md) §2)*

### v03.02.00 — LLM Seam & Persona
**Goal:** Integrate the LLM provider and assemble the contextual prompt.
- **Detailed Tasks:**
  - Build `LLMClient` (e.g., using Google Generative AI SDK for Gemini) hiding the SDK behind a standard `.generate_response(prompt)` interface.
  - Hardcode a system persona: "You are an arrogant Tic-Tac-Toe master. Never lose."
  - Implement a `MemoryWindow` class holding a rolling buffer of the last 10 chat messages and moves.
  - Assemble the prompt template dynamically injecting: Persona + Memory + Current Board State + Valid Moves array.
- **DoD:** When it is the agent's turn, it successfully hits the LLM API with a highly structured contextual prompt.

### v03.03.00 — Tool Calling & Parsing
**Goal:** Translate LLM text outputs into strict WebSocket actions.
- **Detailed Tasks:**
  - Enforce native API Tool Calling (e.g. Gemini Function Calling) OR implement robust regex parsing to extract `{"action": "submit_move", "move": 4}` from raw text.
  - Prevent hallucinated tool calls (e.g., if the LLM picks an invalid cell, retry the generation with an error prompt).
  - Format the final parsed command into JSON and send it over the WebSocket.
- **DoD:** The Agent Client completes a full game of Tic-Tac-Toe autonomously against a dummy opponent.
- **Tests:** Heavily mock the `LLMClient` to return static JSON tool calls, verifying the parser correctly translates them into network payloads.

---

## Phase 4 — Web UI Development
**Goal:** Create the graphical interface for human users and match observation.

### v04.01.00 — HTML/CSS Skeleton
**Goal:** Scaffold the frontend application visuals.
- **Detailed Tasks:**
  - Break the `ui_prototype.html` into a cleaner structure (potentially separating CSS).
  - Implement the Glassmorphism styling (`backdrop-filter`, glowing accents for X and O).
  - Scaffold the CSS Grid for the 3x3 board and the Flexbox layout for the Chat Area sidebar.
- **DoD:** The static HTML renders perfectly in modern browsers without Javascript functionality. *(Ref: [web_ui_specification.md](web_ui_specification.md))*

### v04.02.00 — Native WebSockets & Authentication
**Goal:** Connect the browser to the FastAPI backend.
- **Detailed Tasks:**
  - Write Vanilla JS to hit the `/api/v1/lobby/match` and `/join` endpoints to fetch the Auth Token.
  - Instantiate the native `new WebSocket(url)` object using the token.
  - Define the `ws.onmessage` routing function to switch based on JSON `event` types (`match_state`, `your_turn`, `move_made`, `chat_message`).
- **DoD:** The browser establishes a healthy WebSocket connection, visibly toggling the "Server Status" green dot in the UI header.

### v04.03.00 — Reactive DOM & Chat
**Goal:** Bind network events to visual updates.
- **Detailed Tasks:**
  - **Board:** When `move_made` arrives, locate `document.getElementById('cell-' + index)` and inject the `.x` or `.o` class.
  - **Turns:** When `your_turn` arrives, unlock the grid cells for clicking and apply the `.active` glow to the human player card.
  - **Chat:** Bind the input field's 'Enter' key to `ws.send()`. When `chat_message` arrives, append a styled div to the chat ledger with smooth scrolling.
- **DoD:** A human player can complete a full, real-time match against the Agent CLI strictly through the Web UI.

---

## Phase 5 — Agent Designer & Second Agent
**Goal:** Make agents modular, customizable, and capable of playing against each other.

### v05.01.00 — Designer Schemas
**Goal:** Formalize how agents are defined independently of code.
- **Detailed Tasks:**
  - Create a Pydantic schema `AgentProfile` defining: `name`, `model_type` (e.g., gemini-1.5-pro, claude-3-opus), `temperature`, `system_prompt`, and `memory_limit`.
  - Create sample YAML files (e.g., `profiles/aggressive_bot.yml`, `profiles/defensive_bot.yml`).
- **DoD:** The schema can successfully validate loaded YAML files into Python objects. *(Ref: [architecture.md](architecture.md) §3)*

### v05.02.00 — Generator Engine
**Goal:** Replace hardcoded agent parameters with dynamic configuration.
- **Detailed Tasks:**
  - Refactor the Agent CLI script to accept a `--profile` command line argument.
  - The script dynamically injects the `system_prompt` and selects the `LLMClient` subclass based on the YAML config.
- **DoD:** Running `python agent.py --profile aggressive_bot.yml` successfully connects an agent tailored to those settings.

### v05.03.00 — Agent Swarm
**Goal:** Orchestrate a zero-human game.
- **Detailed Tasks:**
  - Write a shell script (`run_swarm.sh`) that hits the lobby to create a match, then spawns two background instances of `agent.py` using different profiles, pointing them both to the same `match_id`.
- **DoD:** A developer can launch the swarm script, open the Web UI spectator mode, and watch two custom AI agents play Tic-Tac-Toe against each other while bantering in the chat.
