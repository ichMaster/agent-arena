# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

The full roadmap (`spec/roadmap.md`) is **implemented** — all 5 phases, 15 sub-versions, 34 `ARENA-xxx` issues, currently at version `05.03.00` (see `VERSION`/`RELEASE.txt`). `server/`, `client/`, `games/`, `web/`, `profiles/`, `scripts/`, and `tests/` all exist and are exercised by a 130+ test suite. `spec/` remains the planning/reference layer (architecture, game spec, roadmap, and per-issue implementation reports in `spec/implementation/`); `.agents/skills/` and `.claude/skills/` hold the slash-command workflows that built it and that drive any future roadmap work (new games, new phases).

`spec/implementation/code-review-report.md` is a standing record of a post-implementation review — check it (and its "Prioritization" section) before assuming a subsystem is bug-free; several findings from it have been fixed and are noted there, but re-run a review after any nontrivial change to `server/match.py`, `server/websockets.py`, or `server/main.py` specifically, since that's where the trickiest concurrency/identity bugs turned up.

## What Agent Arena is

A modular, turn-based multiplayer game framework where human users and LLM-powered agents (currently Gemini) play the same game against each other in one session. Three cooperating processes:
- **Game Server** (`server/`) — the single source of truth for game state and move legality (FastAPI, WebSockets, SQLAlchemy/SQLite).
- **Agent Client** (`client/agent.py`) — a standalone CLI process that listens for its turn, builds an LLM prompt from a persona/memory window, and pushes back a move via structured tool-call output.
- **Web UI** (`web/`) — a vanilla HTML/CSS/JS "dumb terminal" that renders whatever the server pushes and holds no authoritative state itself.

Full details live in `spec/architecture.md` (component/module breakdown, WebSocket protocol, security model, deployment) and `spec/game_specification.md` (protocol-level spec). `README.md` has the practical "how to run it" version. Read the relevant section before touching a module rather than re-deriving it here.

## Core architectural rules (non-negotiable seams)

- **`GameInterface` is the only way a game plugs in.** Every game module implements `get_state()`, `get_valid_moves()`, `apply_move()`, `is_game_over()` and is otherwise fully decoupled from WebSocket/HTTP logic (`games/interface.py`; `spec/architecture.md` §1, §8, `spec/game_specification.md` §2.4). `games/tictactoe.py` is the first concrete implementation; Russian Checkers/Connect 4/Chess are meant to be added as new modules, not by generalizing Tic-Tac-Toe's code.
- **`LLMClient` is the only way an agent talks to a model vendor.** It's the abstraction seam separating agent logic from a specific SDK (`client/llm.py`). Vendor selection is config-driven via `create_llm_client(model_type, ...)`, keyed off `AgentProfile.model_type` — never import/reference `GeminiClient` (or any future vendor client) directly from `client/agent.py` (`spec/architecture.md` §2).
- **The server is the ultimate authority.** LLM output is untrusted text/tool-calls; every move is re-validated against `GameInterface` server-side regardless of what the agent claims is legal. A client can only submit a move for the player slot (symbol) it's assigned.
- **Match seats are identified by a unique per-connection token (`participant_id`), never by display name.** `server/match.py`'s `Match.assign_symbol` takes the auth token, not `player_name` — two sessions can share a display name (the Web UI defaults everyone to `"Human"`) and must not end up sharing a seat. `player_name` is only for human-readable labels (chat, logs).
- **Everything is event-driven over WebSockets, never polled.** Real events (see `spec/architecture.md` §2): `joined` (once, on connect — carries the assigned symbol), `state_update`, `chat_message`, `game_over`, `error`. Clients react to these; nothing requests state on a timer.
- **The Web UI stores no game state.** It's a pure renderer of server-pushed events — don't add client-side game logic or optimistic state to it.
- **Secrets stay in the Agent process.** LLM API keys live in the agent's `.env` and must never be sent to or logged by the Server or Web UI.
- Any change to a stable seam (WebSocket JSON payload schema, `GameInterface`, `LLMClient` interface) must update `spec/architecture.md` and its contract test in the same commit. This was violated once already (the `joined` event shipped without an architecture.md update) — don't repeat it.

## Testing approach

- LLM calls are always mocked (`google.genai.Client` is patched via `client/llm.py`'s seam) — never hit a paid API in tests or CI, even though a real `GEMINI_API_KEY` may be present in `.env`. Tests must be deterministic and free.
- Game logic (win/loss/draw detection, invalid-move rejection) is tested exhaustively and directly against `GameInterface` implementations, with no server/network involved (`tests/test_tictactoe.py`).
- WebSocket/contract tests pin the shape of push events and the `GameInterface` methods so refactors can't silently break either seam (`tests/test_websockets.py`, `tests/test_server.py`).
- Several tests exercise a **real** `uvicorn` server + real `websockets`/`TestClient` connections (not just mocked units) — see `tests/test_agent.py`'s `live_server` fixture and `tests/test_server.py`'s end-to-end WS tests. Prefer this level for anything touching connection lifecycle (`server/main.py`'s `match_socket`, `ConnectionManager`) — a subtle bug (client disconnect propagating as `CancelledError` instead of `WebSocketDisconnect` when a DB session is open) was only caught this way, not by unit tests.
- Run with `pytest` (repo-wide) or target a file/test, e.g. `pytest tests/test_tictactoe.py`, `pytest tests/test_server.py -k disconnect`. `mypy games/ server/ client/ --config-file mypy.ini` for typing (strict only on `games/*` per `mypy.ini`; `server/`+`client/` are checked but not yet gated strict).

## Working via the roadmap skills

Implementation was driven by four cooperating skills, meant to be run in this order for any future roadmap phase. They live in `.claude/skills/` (Claude Code's project-skill directory, invoked here as `/generate-issues`, `/upload-issues`, etc.) with an equivalent copy kept in `.agents/skills/` for the Antigravity IDE — keep both in sync if you edit one.

1. **`/generate-issues <version>`** (e.g. `/generate-issues v01.01`) — decomposes one roadmap phase (`spec/roadmap.md`) into a dependency-ordered issues file at `spec/implementation/vXX.YY-issues.md`, with globally sequential `ARENA-xxx` IDs.
2. **`/upload-issues @spec/implementation/vXX.YY-issues.md`** — pushes those issues to GitHub one at a time with `vXX.YY::phase` / `size` / `area` labels, and writes back a `vXX.YY-github-report.md` mapping ARENA IDs to issue numbers.
3. **`/execute-issues vXX.YY::phase [--issue ARENA-xxx] [--dry-run]`** — implements issues from GitHub one at a time in dependency order: implement → validate (tests + acceptance criteria, LLM always mocked) → commit → push → close the issue with a summary. Never commits code that fails validation; on failure it reverts (`git checkout -- .`) and asks how to proceed.
4. **`/execute-all-phases`** — the fully local variant used to build this codebase: walks every `spec/implementation/v*-issues.md` in order, implements/validates/commits each issue without touching the GitHub API, and cuts a version release (`VERSION` file, `RELEASE.txt`, git tag `vXX.YY.00`) after each phase completes. See `spec/implementation/execution-time-report.md` for the full timing/bug record of that run.

Rules that apply across all of them:
- **One issue = one commit.** Never mix work from multiple `ARENA-xxx` IDs in a single commit, and never work on more than one issue at a time.
- **Never `git checkout`/cherry-pick code from another branch** to satisfy an issue — every line must be generated fresh by the executing agent in-session. This is enforced explicitly in `execute-all-phases` and applies generally.
- Respect dependency order from each issues file's Dependency Tree; don't start an issue whose dependencies aren't closed/committed yet.
- If an issue's scope is ambiguous, ask rather than guessing.

## Versioning

Strict `vXX.YY.ZZ` tied to roadmap phases: `XX` = roadmap phase (01–05, see `spec/roadmap.md`), `YY` = feature iteration within the phase, `ZZ` = bugfix patch. Releases are tagged `vXX.YY.00` after a phase's issues all land. Currently `05.03.00` — the full original roadmap. Post-review bug-fix work (see `spec/implementation/code-review-report.md`) is tracked separately in `spec/implementation/execution-time-report.md` rather than as new `vXX.YY` releases, since it isn't new roadmap scope.

## Project structure (as implemented)

```
server/    # FastAPI app (main.py), WebSocket ConnectionManager + match routing (websockets.py),
           # match/seat state (match.py), SQLAlchemy models/repository/database, auth token issuance
client/    # Agent CLI (agent.py): WS event loop, LLMClient seam + vendor factory (llm.py),
           # persona/prompt building (prompt.py), memory window (memory.py), AgentProfile (profile.py)
games/     # GameInterface (interface.py) + the TicTacToe engine (tictactoe.py)
web/       # Vanilla HTML/CSS/JS UI (Glassmorphism per spec/web_ui_specification.md), served at /ui
profiles/  # Sample AgentProfile YAML personas (aggressive_bot.yml, cowardly_bot.yml)
scripts/   # run_swarm.sh — orchestrates two agents playing each other, no human involved
tests/     # flat pytest suite (not split into subpackages) mirroring the above by filename
```

Note: earlier drafts of this doc (and `spec/architecture.md` §8) described a target layout with top-level `agent/` and `designer/` directories. That's not what got built — the actual implementation issues scoped everything under `client/` instead, including `AgentProfile` (which `spec/architecture.md` originally assigned to a `designer/` package). This section now reflects reality; don't trust `spec/architecture.md` §8's tree for anything but historical context.

Web UI visual/behavioral fidelity is governed by `spec/ui_prototype.html` (the original design source) and `spec/web_ui_specification.md`.
