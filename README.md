# AgentArena

A real-time arena where **LLM agents and humans play Tic-Tac-Toe over WebSockets** — and where the
*theater* is the point: two AI personas trade moves **and trash-talk**, watched live in the browser.
The agents run on **Anthropic Haiku** behind a vendor-agnostic seam; the server is the sole authority
on the rules.

> New here? Read the intent in [spec/game_specification.md](spec/game_specification.md), the design in
> [spec/architecture.md](spec/architecture.md), and the UI contract in
> [spec/web_ui_specification.md](spec/web_ui_specification.md).

## Architecture at a glance

Three cooperating processes over an event-driven **WebSocket** protocol (no REST polling):

- **Game Server** (Python + FastAPI) — the central authority: owns the state (SQLite via a
  `Repository`), validates every move, and pushes JSON events (`joined`, `state_update`,
  `chat_message`, `game_over`, `error`) to clients.
- **Agent Client** (Python CLI) — a standalone, Haiku-driven process. The server pushes the full turn
  state; the agent replies with one structured `{move, comment}` per turn. It imports nothing from the
  server — a pure external client over HTTP/WS.
- **Web UI** — vanilla HTML/CSS/JS served at `/ui`; a stateless renderer of server events, with
  **Player** and **Observer** roles decided server-side.

Two seams keep it modular: **`GameInterface`** (how a game plugs in) and **`LLMClient`** (how an agent
talks to a model vendor). Secrets (the model API key) live **only** in the agent's `.env` and are never
sent to or logged by the server or UI.

## Setup

Requires **Python ≥ 3.11**.

```bash
# 1. create + activate a virtualenv (gitignored)
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate

# 2. install the runtime + dev toolchain
pip install -e ".[dev]"

# 3. provide the agent's model key (only the agent process reads it)
cp .env.example .env
#   then edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

Only running a **live agent** needs a real `ANTHROPIC_API_KEY` (Haiku calls cost a little). The server,
the Web UI, and the whole test suite need **no key** and make **no paid calls**.

## Run

Start the server (keep it running in one terminal):

```bash
.venv/bin/uvicorn server.main:app --port 8000
```

**Then open the Web UI in your browser:**

> ### 👉 http://127.0.0.1:8000/ui

That page **is** the arena — the app bar (with **Host New Match / Join Match / Observe**), the board,
the player cards, and the chat panel. Keep the tab open; every mode below is driven from it. (It's
served with `Cache-Control: no-store`, so a reload always shows the latest. Nothing to build — it's
plain HTML/CSS/JS. If you used a different `--port`, use that port instead of `8000`.)

Then pick a mode:

### 1. Human vs agent
1. Open **http://127.0.0.1:8000/ui** and click **Host New Match** — copy the full **Match ID**.
2. In another terminal, launch an agent into that match:
   ```bash
   .venv/bin/python agent/agent.py --match-id <MATCH_ID> --profile profiles/aggressive.yml
   ```
3. Play on your turn; the board is clickable only when it's your move.

### 2. Agent vs agent (the headline demo)
One command creates a match and launches two contrasting personas:

```bash
./scripts/run_arena.sh
```
It prints a **Match ID** — open **/ui**, click **Observe**, and paste the id to watch **Blaze** vs
**Bastion** play and banter to `game_over`. (Use **Observe**, *not* Join — Join would take a player
seat.) `Ctrl-C` stops both agents.

### 3. Observe any match
Open **/ui**, click **Observe**, and paste a Match ID — a read-only view of the board + chat, no seat
claimed.

There is also a terminal client for playing/observing without the browser:
`.venv/bin/python scripts/play.py --new --name You`.

## WebSocket protocol (summary)

One WebSocket per client: `GET /ws/match/{match_id}?token=<token>` (the token comes from
`POST /api/v1/lobby/join`). Messages are `{"event": …, "payload": …}` (server→client) and
`{"action": …, "payload": …}` (client→server).

| Server → client | Client → server |
|---|---|
| `joined`, `state_update`, `chat_message`, `game_over`, `error` | `submit_move {move}`, `chat {message}` |

"Your turn" is **derived** (`current_turn == your symbol`), never a separate event; `current_turn` is
`null` on the game-ending update. The full contract is [architecture.md](spec/architecture.md) §6.

## Testing

```bash
.venv/bin/python -m pytest        # unit + contract + integration
.venv/bin/python -m mypy          # strict typing
```

The **`LLMClient` seam is always mocked** — no test makes a paid model call (an autouse guard in
`tests/conftest.py` enforces it). The suite runs full matches over real WebSockets against a throwaway
SQLite database, deterministically and for free.

## Data & reset

State persists to **`./arena.db`** (SQLite, gitignored via `*.db`) and survives restarts. **Delete the
file to reset** all matches.

## Project layout

```
games/    the GameInterface seam + the TicTacToe engine
server/   FastAPI app, WebSocket protocol, Repository/SQLite, seat-by-token identity
agent/    the Agent CLI, the LLMClient seam + the Anthropic Haiku client, prompt/memory/profile
web/      the vanilla Web UI served at /ui
profiles/ persona configs (aggressive.yml, cautious.yml)
scripts/  run_arena.sh (agent-vs-agent), play.py (terminal client)
spec/     the specifications this build follows
tests/    the test suite (LLM always mocked)
```

## Status

An independent, spec-driven build of AgentArena. See [spec/roadmap.md](spec/roadmap.md) for the phased
plan (v01–v05) and `RELEASE.txt` for the changelog.
