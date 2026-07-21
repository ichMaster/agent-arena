# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Branch state — read this first

This branch (`Anthropic-Opus4.8-Opus4.8-dev`) is a **planning seed, not an implemented codebase.** It
was branched from a **cleaned-up `main`** and tracks only:

- `spec/game_specification.md` — the product vision + MVP scope + phased plan (the single source of intent).
- `spec/architecture.md` — the detailed technical design (module layout, seams, wire contracts, identity model).
- `spec/roadmap.md` — the 5-version / 15-phase build plan (`vXX.YY` phases, each with Goal/Tasks/DoD/Tests).
- `spec/web_ui_specification.md` + `spec/ui_prototype.html` — the Web UI's behavioral spec and visual design source.
- `spec/implementation/vXX.YY-issues.md` — **already-generated**, per-phase issue breakdowns for all 15
  phases (v01.01 → v05.03). Their `ARENA-OPUS-###` ids and acceptance criteria describe *another*
  build's implementation choices — treat them as a strong draft, not gospel; verify against the specs
  above and correct drift (see `reconcile-issues` below) before executing.
- `.claude/skills/*` — ten SDLC skills that build the repo (below).
- `.gitignore` — currently just `.env` (the build should extend it: `.venv/`, `__pycache__/`, `*.db`, caches).

There is **no `server/`, `agent/`, `games/`, `web/`, `tests/`, `pyproject.toml`, `VERSION`, `README.md`,
`.env.example`, or `.agents/` yet** — they are meant to be *generated on this branch* to build Agent
Arena using Anthropic **Haiku**-powered game agents (per `spec/game_specification.md` §3, called
`LLMClient`/`AnthropicHaikuClient` in `spec/architecture.md` §4.2, §7). The game agent's model is
**always Haiku**, independent of this branch's name. Do not assume any module exists; check first.

> **Critical rule — never copy from sibling branches.** The current siblings on this remote
> (`origin`, `ichMaster/agent-arena`) are `Anthropic-Opus4.8-dev`, `Anthropic-Opus4.8-Sonet5-dev`,
> `Anthropic-Gemini3.1Pro-Sonet5-dev`, `Gemini-3.1Pro-dev`, `Gemini-3.1Pro-3.1Pro-dev`,
> `Gemini-3.1Pro-3.5Flash-dev` — each a *complete, working implementation* of this same spec. The
> entire point of this branch is an independent build: **every line of code, test, script, and config
> must be generated fresh in-session.** Never `git checkout`, `git cherry-pick`, `git merge`, or
> otherwise copy files/code from another branch (or its GitHub issues) to satisfy work here.

## Namespace — decide before the first release/upload

The pre-generated issues use the **`ARENA-OPUS-###`** id namespace, and the natural release-tag prefix
would be `opus-`. **Both are already taken on the shared remote** by the sibling `Anthropic-Opus4.8-dev`
branch — it has uploaded `ARENA-OPUS-###` GitHub issues and pushed `opus-vXX.YY.ZZ` release tags
(plain `vXX.YY.ZZ` tags from another sibling also exist, and `opus-sonnet-vXX.YY.ZZ` was used by the
`Anthropic-Opus4.8-Sonet5-dev` branch). This branch therefore needs its **own** distinct issue-id
prefix (if using workflow B) and release-tag prefix **before** `upload-issues`/`release-version` run
for the first time — **ask the user** rather than inventing one. The established pattern is
`<short-tag>-vXX.YY.ZZ` (e.g. the sibling used `opus-` and `opus-sonnet-`); a fitting choice here would
be a variant that doesn't collide (confirm with the user). Rename the `ARENA-OPUS-###` ids in the
issues files to the chosen prefix during reconciliation if you rename at all.

## Commit / co-author trailer

This branch is coded by **Opus 4.8**. End commit messages with:

```
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

Commits and tags are **only pushed when the user asks.** (The sibling `Anthropic-Opus4.8-Sonet5-dev`
build ran commit-only end-to-end and pushed at the very end on request — mirror whatever the user
specifies for this run.)

## Two build workflows — pick one deliberately

Both are in `.claude/skills/`; they are not meant to be mixed within one version.

**A. File-driven, offline (uses the issues files already on this branch):**
`reconcile-issues vXX.YY` (correct the pre-generated issues file against the real code, in place, with
a dated `⟳ Reconciled` mark — no code written) → `execute-issues-file vXX.YY` (implement straight from
the file: implement → validate → commit → push per issue, dependency-ordered, **no GitHub**) →
`review-and-fix-issues vXX.YY` → `release-version vXX.YY.00`. Orchestrated end-to-end (all phases, one
final timed statistics report) by **`/ship-solution`**.

**B. GitHub-driven (mirrors the sibling branches' workflow):**
`generate-issues` → `upload-issues` → `execute-issues` (implements from real GitHub issues, closes them
as it goes) → `review-and-fix-issues` → `release-version`. Orchestrated per phase/version, with
per-phase chat reports and an opt-in end-of-phase hardening sweep, by **`/ship-phase`**.

> Before using workflow B: this branch's issue-id prefix and release-tag prefix are **not yet chosen**
> — see "Namespace" above. Decide them with the user before the first `upload-issues`/`release-version`.

Rules that hold across all skills, either workflow:
- **One issue = one commit.** Never mix work from multiple issue IDs; never work on more than one at a time.
- **Respect the Dependency Tree** in each issues file — don't start an issue whose dependencies aren't committed.
- **Tests ship with the feature**, and **the LLM is always mocked** in tests — never make a paid model call in tests/validation/CI.
- **A seam change** (WebSocket payload schema, `GameInterface`, `LLMClient`, seat-by-token identity) **updates `spec/architecture.md` + its contract test in the same commit.**
- If an issue's scope is ambiguous, or the pre-generated issues file disagrees with the real code/specs, ask or reconcile rather than guessing.
- `release-version`/`harden-findings` never bump the version or release without it being an explicit, confirmed step.

## Target architecture (from `spec/game_specification.md` + `spec/architecture.md`)

Three cooperating processes over an **event-driven WebSocket** protocol (no REST polling):

- **Game Server** (Python + FastAPI) — central authority: owns authoritative state (SQLite via a
  `Repository`), validates every move, pushes JSON events (`joined`, `state_update`, `chat_message`,
  `game_over`, `error`) to clients. Holds a `ConnectionManager` mapping `match_id` → connected sockets.
  "Your turn" is a *derived* condition (`current_turn == your symbol`), not a separate event; live game
  state is **reconstructed by replaying the move log**, never stored as mutable fields.
- **Agent Client** (Python CLI) — standalone LLM-driven process (Anthropic Haiku). The server pushes
  full turn state; the agent replies with **one structured `{move, comment}`** per turn (no pull-tools
  round-trip), with a bounded retry-then-random-legal-fallback if the model hallucinates a move.
  Imports nothing from `server/` — a pure external client over HTTP/WS.
- **Web UI** — vanilla HTML/CSS/JS served at `/ui`, no build step; a stateless renderer of server
  events, with **Player** and **Observer** roles decided server-side (never asserted by the client).

Two seams are the whole point of the design — keep them clean:

- **`GameInterface`** (§4.1) is the only way a game plugs in: `get_state()`, `get_valid_moves()`,
  `apply_move(move)`, `is_game_over()`. `apply_move` is the sole legality authority and never raises on
  bad input. Tic-Tac-Toe is the first implementation; future games (Checkers, Connect 4, Chess) are
  added as new modules, not by generalizing Tic-Tac-Toe. The move payload is opaque to transport.
- **`LLMClient`** (§4.2) is the only way an agent talks to a model vendor — the abstraction
  (`create_llm_client`, `AnthropicHaikuClient` the only impl) that lets the vendor be swapped by
  config, keeping agent logic free of any specific SDK.

Non-negotiables: the **server is the ultimate authority** (LLM output is untrusted; re-validate every
move server-side); **seats are keyed by per-connection token, never display name** (`UNIQUE(match_id,
symbol)`; observers never hold a seat, permanently); **secrets (model API keys) live only in the
agent's `.env`** and are never sent to or logged by the server/UI; WS cleanup runs in a `finally` block
(a client-initiated drop can surface as async cancellation, not `WebSocketDisconnect`, so shield the
seat release); an **Agent Designer** (`AgentProfile` YAML — name/system_prompt/model_type/temperature/
memory_limit) packages a persona/model/memory config into a runnable agent.

## Tech & style

- Python + FastAPI + WebSockets for the server; Python for the agent CLI; vanilla HTML/CSS/JS (no build
  step) for the Web UI, served at `/ui` with `Cache-Control: no-store`.
- Persistence: **SQLite** via SQLAlchemy (async + `aiosqlite`) behind a `Repository`; four tables
  (`matches`, `participants`, `moves`, `chat_messages`); live state reconstructed from the move log
  (no serialize seam on `GameInterface`).
- **Use strict typing in Python** throughout `games/`, `server/`, `agent/`.

## Commands (once code exists)

No build/test tooling is committed on this branch yet; these are the conventions the skills assume:

- Tests: `pytest` (repo-wide) or a single file/test, e.g. `pytest tests/test_tictactoe.py` or
  `pytest tests/test_server.py -k <expr>`.
- Typing: `mypy` (strict; `[tool.mypy] strict = true`, `files = ["games","server","agent"]` in
  `pyproject.toml` works well — no separate `mypy.ini` needed).
- Local dev deps in a `.venv/` (gitignored); server runs under `uvicorn server.main:app` — declare
  `uvicorn` as a **runtime dependency** (plain `fastapi` does not pull it in).
- **Packaging gotcha:** if `pyproject.toml` declares no `[build-system]`/`[tool.setuptools]` package
  list, `pip install -e ".[dev]"` fails with *"Multiple top-level packages discovered in a
  flat-layout"* — setuptools auto-discovers `web/`, `profiles/`, `spec/`, etc. as false package
  candidates. Pin `[tool.setuptools] packages = ["games", "server", "agent"]` explicitly.
- SQLite `*.db` files and caches should be gitignored; the DB path is config-driven (`./arena.db`).

## Versioning

Strict `vXX.YY.ZZ` tied to roadmap phases: `XX` = roadmap version (v01–v05), `YY` = phase within it,
`ZZ` = bugfix/patch on that phase. Releases are cut per **version** (`vXX.YY.00`), after that version's
issues all land and its tests are green — **never bump the version without explicit user
confirmation.** This branch's release-tag prefix (and, for workflow B, its issue-id prefix) is **not
yet chosen** — decide it with the user before the first `release-version`/`upload-issues` call (see
"Namespace" above).
