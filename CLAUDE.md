# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Branch state — read this first

This branch (`Anthropic-Opus4.8-dev`) is a **planning seed, not an implemented codebase.** It contains only:

- `spec/game_specification.md` — the product vision + MVP scope + phased plan (the single source of intent).
- `spec/architecture.md` — the detailed technical design (module layout, seams, wire contracts, identity model).
- `spec/roadmap.md` — the 5-version / 15-phase build plan (`vXX.YY` phases, each with Goal/Tasks/DoD/Tests).
- `spec/web_ui_specification.md` + `spec/ui_prototype.html` — the Web UI's behavioral spec and visual design source (govern `web/` fidelity).
- `.claude/skills/*` — the four SDLC skills that build the repo.
- `README.md`, `CLAUDE.md`, `.gitignore`.

There is **no `server/`, `agent/`, `games/`, `web/`, `tests/`, `requirements.txt`, or `VERSION` yet** — they are meant to be *generated from scratch on this branch* to build Agent Arena using Anthropic **Haiku**-powered agents (per `spec/game_specification.md` §3). Do not assume any module exists; check first.

> **Critical rule — never copy from sibling branches.** Sibling branches (`Anthropic-Gemini3.1Pro-Sonet5-dev`, `Gemini-3.1Pro-*`, etc.) contain a *complete, working implementation* of this same spec. The entire point of this branch is an independent build: **every line of code, test, script, and config must be generated fresh in-session.** Never `git checkout`, `git cherry-pick`, `git merge`, or otherwise copy files/code from another branch to satisfy work here. This is also stated in `.claude/skills/execute-issues/SKILL.md`.

## The build workflow (four skills, run in order)

The repo is built by driving the four SDLC skills in `.claude/skills/`. `spec/roadmap.md` is
already authored — each `### vXX.YY` phase carries the Goal/Tasks/DoD the skills consume.

1. **`/generate-issues <vXX.YY>`** — decomposes one roadmap phase into a dependency-ordered issues file at `spec/implementation/vXX.YY-issues.md`, with globally-sequential `ARENA-xxx` IDs (continuing across phase files). Writes the local file only; does not touch GitHub.
2. **`/upload-issues @spec/implementation/vXX.YY-issues.md`** — pushes those issues to GitHub one at a time with `vXX.YY::phase` / `size` / `area` labels via `gh`, and writes back a `vXX.YY-github-report.md` mapping ARENA IDs → issue numbers.
3. **`/execute-issues vXX.YY::phase [--issue ARENA-xxx] [--dry-run]`** — GitHub-driven: implement → validate (`pytest`+`mypy`, LLM mocked) → commit → **push** → close each issue in dependency order, then write a `vXX.YY-execution-report.md`.
4. **`/release-version vXX.YY.00 [changelog…]`** — after a phase's issues all land: bump `VERSION`, update `README.md` + the FastAPI app version, prepend `RELEASE.txt`, commit, annotated-tag `vXX.YY.00`, and push. Never bumps the version without explicit confirmation.

Rules that hold across all skills:
- **One issue = one commit.** Never mix work from multiple `ARENA-xxx` IDs; never work on more than one issue at a time.
- **Respect the Dependency Tree** in each issues file — don't start an issue whose dependencies aren't committed/closed.
- **Tests ship with the feature**, and **the LLM is always mocked** in tests — never make a paid model call in tests/validation/CI.
- **A seam change (WebSocket payload schema, GameInterface, LLMClient, seat-by-token identity) updates `spec/architecture.md` + its contract test in the same commit.**
- If an issue's scope is ambiguous, ask rather than guess.

## Target architecture (from `spec/game_specification.md`)

Three cooperating processes over an **event-driven WebSocket** protocol (no REST polling):

- **Game Server** (Python + FastAPI) — central authority: owns authoritative state (SQLite via a `Repository`), validates every move, pushes JSON events (`joined`, `state_update`, `chat_message`, `game_over`, `error`) to clients. Holds a Connection Manager mapping `match_id` → connected sockets. "Your turn" is a *derived* condition (`current_turn == your symbol`), not a separate event.
- **Agent Client** (Python CLI) — standalone LLM-driven process (Anthropic Haiku). The server pushes full turn state; the agent replies with **one structured `{move, chat}`** per turn (no pull-tools round-trip). Imports nothing from `server/` — a pure external client over HTTP/WS.
- **Web UI** — vanilla HTML/CSS/JS served at `/ui`; a stateless renderer of server events, with **Player** and **Observer** roles decided server-side.

Two seams are the whole point of the design — keep them clean:

- **`GameInterface`** is the only way a game plugs in: `get_state()`, `get_valid_moves()`, `apply_move(move)`, `is_game_over()`. Tic-Tac-Toe is the first implementation; future games (Checkers, Connect 4, Chess) are added as new modules, not by generalizing Tic-Tac-Toe.
- **`LLMClient`** is the only way an agent talks to a model vendor — the abstraction that lets the vendor be swapped by config, keeping agent logic free of any specific SDK.

Non-negotiables: the **server is the ultimate authority** (LLM output is untrusted; re-validate every move server-side); **secrets (model API keys) live only in the agent's `.env`** and are never sent to or logged by the server/UI; an **Agent Designer** packages a persona/model/memory config into a runnable agent.

## Tech & style

- Python + FastAPI + WebSockets for the server; Python for the agent CLI; vanilla HTML/CSS/JS (no build step) for the Web UI, served at `/ui`.
- Persistence: **SQLite** via SQLAlchemy (async + `aiosqlite`) behind a `Repository`; live game state reconstructed from the move log.
- **Use strict typing in Python.**

## Commands (once code exists)

No build/test tooling is committed on this branch yet; these are the conventions the skills assume, and what to (re)establish when scaffolding:

- Tests: `pytest` (repo-wide) or a single file/test, e.g. `pytest tests/test_tictactoe.py` or `pytest tests/test_server.py -k <expr>`.
- Typing: `mypy` (the skills call for strict typing; add a `mypy.ini` when scaffolding).
- Local dev deps live in a `.venv/` (gitignored); server runs under `uvicorn`. SQLite `*.db` files and caches are gitignored.

## Versioning

Strict `vXX.YY.ZZ` tied to roadmap phases: `XX` = roadmap version (v01–v05), `YY` = phase within it, `ZZ` = bugfix patch. Releases are tagged `vXX.YY.00` after a phase's issues all land (handled by `/release-version`).
