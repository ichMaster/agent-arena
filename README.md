# Agent Arena

A modular, turn-based multiplayer game framework where human players and LLM-powered AI agents (currently Google Gemini) play against each other in real time over WebSockets. The reference game is Tic-Tac-Toe, built behind a pluggable `GameInterface` so new games can be added without touching the server or transport layer.

**Status:** the full roadmap (`spec/roadmap.md`) is implemented — all 5 phases, 15 sub-versions, 34 issues — currently at **v05.03.00**, 113 passing tests. See `spec/implementation/execution-time-report.md` for the full build history and `RELEASE.txt` for a phase-by-phase changelog.

## Architecture

Three independent processes talk over HTTP/WebSocket, matching `spec/architecture.md`:

- **Game Server** (`server/`) — FastAPI + WebSockets. The sole source of truth for game state; every move is re-validated server-side regardless of what a client claims. Persists matches/moves/chat to SQLite via SQLAlchemy (`server/database.py`, `server/models.py`, `server/repository.py`).
- **Agent Client** (`client/`) — a standalone CLI process that joins a match, listens for its turn, builds a persona-driven prompt from recent match history, asks Gemini for a move via structured JSON output, validates/retries, and submits it back over the socket.
- **Web UI** (`web/`) — a dependency-free HTML/CSS/JS single page. It holds no authoritative game state; it only renders whatever the server pushes and sends `submit_move`/`chat` actions back.

Games plug in by implementing `games/interface.py`'s `GameInterface` (`get_state`, `get_valid_moves`, `apply_move`, `is_game_over`); `games/tictactoe.py` is the only current implementation. LLM vendors plug in the same way via `client/llm.py`'s `LLMClient` seam; `GeminiClient` is the only current implementation.

### WebSocket protocol

Clients connect to `ws://<server>/ws/match/{match_id}?token=<token>` (token from `POST /api/v1/lobby/join`). Server-pushed events:

| Event | Sent | Payload |
|---|---|---|
| `joined` | once, right after connecting | `symbol` (this connection's assigned X/O — assigned by connection order), `board`, `current_turn`, `valid_moves` |
| `state_update` | after every valid move | `board`, `current_turn`, `valid_moves`, `last_move` |
| `chat_message` | after a chat action | `sender`, `message` |
| `game_over` | when the game ends | `result` (`"X"` / `"O"` / `"draw"`) — the server then closes every connection in the room |
| `error` | on an invalid/malformed message | `detail` |

Client-sent actions: `{"action": "chat", "payload": {"message": "..."}}` and `{"action": "submit_move", "payload": {"move": <0-8>}}`.

## Project layout

```
server/     FastAPI app, WebSocket connection manager, match orchestration, SQLAlchemy persistence
client/     Agent CLI: WS event loop, Gemini LLMClient, prompt/persona/memory, AgentProfile loader
games/      GameInterface + the TicTacToe engine
web/        Static HTML/CSS/JS UI, served by the app at /ui
profiles/   Sample AgentProfile YAML personas (aggressive_bot.yml, cowardly_bot.yml)
scripts/    run_swarm.sh — orchestrates two agents playing each other
tests/      pytest suite (113 tests) — LLM calls are always mocked, never hit the real API
spec/       Architecture/game/roadmap specs and per-issue implementation reports
```

## Setup

Requires Python 3.14 (or adjust the pinned dependency versions in `requirements.txt` for your interpreter — the originally-planned pins needed a Rust toolchain to build from source on 3.14, so this repo pins versions with prebuilt wheels instead).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt        # add -r requirements-dev.txt for mypy too
```

Create a `.env` file in the repo root (gitignored) with your Gemini API key — the agent CLI fails fast at startup if this is missing:

```
GEMINI_API_KEY=your-key-here
```

## Running it

**1. Start the server** (also serves the Web UI at `/ui`):

```bash
uvicorn server.main:app --reload
```

Open `http://localhost:8000/ui` in a browser — click **Host New Match** (or **Join Match** with an existing Match ID), enter a name, and play. The board only becomes clickable on your turn. To watch a match without playing (e.g. two agents launched by the swarm script below), use **Spectate Match** instead — unlike Join Match, it never claims one of the two player seats.

**2. Run a single agent** against that match (find the Match ID from the UI header or the lobby response):

```bash
python client/agent.py --match-id <MATCH_ID> --profile profiles/aggressive_bot.yml
```

`--profile` is required and selects the agent's persona, temperature, and memory window (see `client/profile.py` / `AgentProfile`). `--symbol X|O` is optional — the server actually assigns symbols by connection order, so this only warns if the assignment doesn't match what you expected. `--player-name` overrides the profile's own `name`.

**3. Or run two agents against each other with no human involved:**

```bash
./scripts/run_swarm.sh
```

Creates a match, prints the spectator UI link, waits for you to press Enter, then launches `aggressive_bot.yml` (X) against `cowardly_bot.yml` (O) as background processes and tails both logs until you press Ctrl+C.

## Known limitations

A post-implementation review (`code-review` skill, high effort — 8 finder angles + independent verification, all 10 surviving findings CONFIRMED) surfaced real gaps not yet fixed:

- **Seats are identified by player name, not connection.** `Match.assign_symbol` keys a seat by the raw name string. The Web UI defaults every session's name prompt to `"Human"`, so two different people who both accept the default and join the same match silently share one seat — both can move as the same symbol, and their chat is indistinguishable.
- **A disconnect mid-game permanently strands the match.** No player-symbol entry is ever released on disconnect (only on `game_over`), so a crashed/closed tab leaves that seat unrecoverable short of restarting the whole server (which drops every other concurrent match too).
- **`scripts/run_swarm.sh`'s X/O assignment is a race**, not a guarantee. Symbols are assigned by whichever agent's WebSocket connects first, not by `--symbol` — the two launched processes have no synchronization, so which persona actually plays which side can flip. `--symbol` mismatches only produce a `stderr` warning in a log file.
- **`POST /api/v1/lobby/join` doesn't check the match exists**, so a bad `match_id` (e.g. a typo'd `--match-id`) joins successfully but crashes the connection with an uncaught DB error on the first chat/move.
- `AgentProfile.model_type` is defined but unused — `client/agent.py` always hardcodes `GeminiClient` rather than selecting a vendor from it, so swapping LLM providers currently requires a code change, not just a YAML edit.
- `spec/architecture.md` still documents a `your_turn` event that was never implemented, and doesn't document the real `joined` event the WS protocol actually uses.
- `CLAUDE.md`'s documented project structure (top-level `agent/`, `designer/`) doesn't match reality — the code lives under `client/` instead, per how the implementation issues were actually scoped.

None of these block normal single-match human-vs-agent or agent-vs-agent play; they matter most for concurrent multi-match usage, unreliable networks, and true multi-vendor LLM support.

## Testing

```bash
pytest                          # full suite, 113 tests
pytest tests/test_tictactoe.py  # a single file
mypy games/ --config-file mypy.ini
```

LLM calls are always mocked (`google.genai.Client` is patched in every test) — the suite never hits the real Gemini API or spends quota, per `CLAUDE.md`'s testing rules.

## Documentation

- [`spec/architecture.md`](spec/architecture.md) — component architecture, security model, deployment
- [`spec/game_specification.md`](spec/game_specification.md) — protocol-level specification
- [`spec/web_ui_specification.md`](spec/web_ui_specification.md) — Web UI design system
- [`spec/roadmap.md`](spec/roadmap.md) — the phased build plan this codebase implements
- [`spec/implementation/`](spec/implementation/) — per-issue and per-phase execution reports, plus the full [execution-time-report.md](spec/implementation/execution-time-report.md)
- [`CLAUDE.md`](CLAUDE.md) — guidance for AI agents working in this repo
