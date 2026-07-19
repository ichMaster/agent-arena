# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Branch state — read this first

This branch (`Anthropic-Opus4.8-dev`) is a **planning seed, not an implemented codebase.** It contains only:

- `spec/game_specification.md` — the product/architecture spec (the single source of intent).
- `.agents/` — the skill workflow (`.agents/skills/*`) and `.agents/AGENTS.md` (rules for the Antigravity IDE).
- `README.md`, `.gitignore`.

There is **no `server/`, `client/`/`agent/`, `games/`, `web/`, `designer/`, `tests/`, `requirements.txt`, or `VERSION` yet** — they are meant to be *generated from scratch on this branch* to build Agent Arena using Anthropic **Haiku**-powered agents (per `spec/game_specification.md` §3). Do not assume any module exists; check first.

> **Critical rule — never copy from sibling branches.** Sibling branches (`Anthropic-Gemini3.1Pro-Sonet5-dev`, `Gemini-3.1Pro-*`, etc.) contain a *complete, working implementation* of this same spec. The entire point of this branch is an independent build: **every line of code, test, script, and config must be generated fresh in-session.** Never `git checkout`, `git cherry-pick`, `git merge`, or otherwise copy files/code from another branch to satisfy work here. This is also stated in `.agents/skills/execute-all-phases/SKILL.md`'s Strict Implementation Rule.

## The build workflow (four skills, run in order)

The repo is built by driving four skills. They live in `.agents/skills/` (for the Antigravity IDE). If you invoke them as Claude Code slash-commands, mirror them into `.claude/skills/` first and keep both copies in sync.

1. **Author the phase-planning docs the skills consume.** `generate-issues` decomposes a *phase plan* derived from `spec/game_specification.md` — that planning layer must be written first (there is nothing on this branch to decompose yet). Follow the paths each skill actually references when you scaffold it.
2. **`/generate-issues <vXX.YY>`** — decomposes one phase into a dependency-ordered issues file at `spec/implementation/vXX.YY-issues.md`, with globally-sequential `ARENA-xxx` IDs (continuing across phase files). Writes the local file only; does not touch GitHub.
3. **`/upload-issues @spec/implementation/vXX.YY-issues.md`** — pushes those issues to GitHub one at a time with `vXX.YY::phase` / `size` / `area` labels via `gh`, and writes back a `vXX.YY-github-report.md` mapping ARENA IDs → issue numbers.
4. **Implement**, via one of:
   - **`/execute-issues vXX.YY::phase [--issue ARENA-xxx] [--dry-run]`** — GitHub-driven: implement → validate → commit → **push** → close each issue in dependency order.
   - **`/execute-all-phases`** — fully local: walks every `spec/implementation/v*-issues.md`, implements/validates/commits each issue **without any GitHub API calls**, and cuts a `vXX.YY.00` release (updates `VERSION`, appends `RELEASE.txt`, tags `vXX.YY.00`) after each phase.

Rules that hold across all skills:
- **One issue = one commit.** Never mix work from multiple `ARENA-xxx` IDs; never work on more than one issue at a time.
- **Respect the Dependency Tree** in each issues file — don't start an issue whose dependencies aren't committed/closed.
- **Tests ship with the feature**, and **the LLM is always mocked** in tests — never make a paid model call in tests/validation/CI.
- **A seam change (WebSocket payload schema, GameInterface, LLMClient) updates the relevant spec doc + its contract test in the same commit.**
- If an issue's scope is ambiguous, ask rather than guess.

## Target architecture (from `spec/game_specification.md`)

Three cooperating processes over an **event-driven WebSocket** protocol (no REST polling):

- **Game Server** (Python + FastAPI) — central authority: owns authoritative game state, validates every move, pushes JSON events (`your_turn`, `chat_message`, …) to clients. Holds a Connection Manager mapping `match_id` → connected sockets.
- **Agent Client** (Python CLI) — standalone LLM-driven process (Anthropic Haiku). Waits for a `your_turn` event, builds a prompt from persona + memory window + board/valid-moves, and pushes an action back. It acts through tools: `get_valid_moves()`, `submit_move(move)`, `send_chat_message(message)`, `get_game_status()`.
- **Web UI** — human player view + admin/observer view; renders server-pushed state, holds no authoritative game state.

Two seams are the whole point of the design — keep them clean:

- **`GameInterface`** is the only way a game plugs in: `get_state()`, `get_valid_moves()`, `apply_move(move)`, `is_game_over()`. Tic-Tac-Toe is the first implementation; future games (Checkers, Connect 4, Chess) are added as new modules, not by generalizing Tic-Tac-Toe.
- **`LLMClient`** is the only way an agent talks to a model vendor — the abstraction that lets the vendor be swapped by config, keeping agent logic free of any specific SDK.

Non-negotiables: the **server is the ultimate authority** (LLM output is untrusted; re-validate every move server-side); **secrets (model API keys) live only in the agent's `.env`** and are never sent to or logged by the server/UI; an **Agent Designer** packages a persona/model/memory config into a runnable agent.

## Tech & style (from `.agents/AGENTS.md`)

- Python + FastAPI + WebSockets for the server; Python for the agent CLI; Web UI stack TBD.
- **Use strict typing in Python.**

## Commands (once code exists)

No build/test tooling is committed on this branch yet; these are the conventions the skills assume, and what to (re)establish when scaffolding:

- Tests: `pytest` (repo-wide) or a single file/test, e.g. `pytest tests/test_tictactoe.py` or `pytest tests/test_server.py -k <expr>`.
- Typing: `mypy` (the skills call for strict typing; add a `mypy.ini` when scaffolding).
- Local dev deps live in a `.venv/` (gitignored); server runs under `uvicorn`. SQLite `*.db` files and caches are gitignored.

## Versioning

Strict `vXX.YY.ZZ` tied to roadmap phases: `XX` = roadmap phase, `YY` = feature iteration within the phase, `ZZ` = bugfix patch. Releases are tagged `vXX.YY.00` after a phase's issues all land (handled by `execute-all-phases`).
