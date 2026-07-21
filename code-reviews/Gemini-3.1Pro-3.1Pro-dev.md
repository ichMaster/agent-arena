# Branch Review: `origin/Gemini-3.1Pro-3.1Pro-dev` (spec: Gemini 3.1 Pro, code: Gemini 3.1 Pro)

## 1. INVENTORY

**Python source (616 LOC total):**
- `games/` — 72 LOC: `interface.py` (20), `tictactoe.py` (51), `__init__.py` (1)
- `server/` — 307 LOC: `main.py` (93), `websockets.py` (72), `repository.py` (43), `models.py` (42), `init_db.py` (39), `database.py` (18)
- `client/` — 237 LOC: `agent.py` (169), `llm.py` (47), `profile.py` (21)

**Frontend (639 LOC):** `frontend/app.js` (188), `index.html` (97), `styles.css` (354). No build step, served via `StaticFiles` at `/`.

**Tests:** 6 files, 287 LOC, **19 test functions**: `test_tictactoe.py` (8), `test_server.py` (4), `test_websockets.py` (3), `test_database.py` (2), `test_match_lifecycle.py` (1), `test_games.py` (1). No `client/` tests at all.

**Config:** `requirements.txt` (15 deps, **unpinned** — roadmap v01.01 explicitly required "locking versions"), `mypy.ini` (strict=True), `.gitignore`, `VERSION` (05.03.00), `RELEASE.txt` (all 15 versions). No pyproject.toml, no CI, no Dockerfiles/docker-compose (architecture.md §7 promises both).

**README:** good — features, accurate structure tree, setup, test/mypy commands, two run modes (swarm, human-vs-AI) with the `--symbol`/`--first-move` workaround documented. One of the better READMEs for this size.

**Hygiene / granularity:** 26 commits total; 7 predate code. The 34 issue IDs (ARENA-001…034) land in ~15 commits, routinely **2–4 issues per commit** (e.g. `e26da40` "ARENA-008 to ARENA-011") — per-issue bisection/traceability is impossible. Release commits exist only for Phase 1; v02–v05 releases are tags + RELEASE.txt only. Both `errors.md` (raw 8-line scratch list) **and** `post-code-generation-errors.md` (formatted, 9 incidents) sit in root and disagree on counts; `errors.md` is leftover clutter from commit `6b15903`.

## 2. CODE REVIEW

**Strengths**
- Clean `GameInterface` ABC (`games/interface.py`) matching this branch's own roadmap; `TicTacToe.apply_move` is a genuine single legality authority: type, bounds, occupancy, turn, and game-over all checked, never raises (`games/tictactoe.py`).
- Server does re-validate every move via `game.apply_move` and rejects with an `error` event (`server/main.py`); spectators get no symbol so their moves fail closed.
- `LLMClient` ABC + `GeminiClient` with structured Pydantic output (`response_schema=AgentResponse`) in `client/llm.py`; agent has a 3-retry loop with corrective re-prompting and a random-legal-move fallback (`client/agent.py`) — solid hallucination handling.
- Repository pattern + async SQLite with FK pragma enforced and tested (`server/database.py`, `tests/test_database.py`); YAML profile → Pydantic `AgentProfile` works end-to-end.

**Weaknesses (severe)**
- **The database is dead code in the live path.** `server/main.py` never imports `Repository`; matches, moves, and chat are never persisted during gameplay. architecture.md §4's "every applied move is checkpointed… rehydrates matches on boot" is entirely unimplemented. `init_db.py` is a manual demo script.
- **Identity/authority holes.** Tokens are a global `valid_tokens` set, unbound to match or player; `/lobby/join` mints a token for any match_id. Seats are keyed by the **WebSocket object** (`player_symbols: dict[WebSocket, str]`), not token — a reconnect loses the seat. Worst: the `first_move` query param lets **any connecting client mutate `game.current_turn` mid-game** (`server/websockets.py` `connect()`); any client can also claim a symbol via `?symbol=X`.
- **Shipped with a broken test suite.** The final manual commit `79a2dc1` flipped the engine default `current_turn` from "X" to "O" (`games/tictactoe.py`) without touching tests. At HEAD, **8 of 19 tests fail** (7 in `test_tictactoe.py`, plus `test_match_lifecycle.py`, which expects O's first move to be rejected). The stats file's "19 tests passed" is only true of a pre-fix commit.
- **WS cleanup is not in `finally`.** Cleanup runs only in `except WebSocketDisconnect`; the inner `except Exception: break` path leaks the socket in `active_connections`, and `broadcast()` has no per-connection error handling — one dead socket aborts the broadcast for everyone (`server/main.py`, `server/websockets.py`).
- **XSS.** `renderChat()` uses `innerHTML` with raw user/LLM chat content (`frontend/app.js`) — an agent comment containing `<img onerror=…>` executes in every viewer's browser.
- **Typing claims not credible.** mypy.ini is strict, but code has implicit-Optional defaults (`token: str = None`, `symbol: str = None`), missing return annotations throughout `server/websockets.py` and `client/agent.py`, and a `# type: ignore` on the core move call — strict mypy over `server/ client/` cannot plausibly pass as claimed ("0 issues").
- **Testing gaps:** zero client/agent tests, so the LLM is "mocked" only by absence; no DB↔server integration test; `ClientActionPayload.payload` is `typing.Any`, so the only real Pydantic validation is the envelope. LLM seam swap is not config-driven — `GeminiClient` is hardcoded in `agent.py` (no factory).

## 3. SPEC QUALITY — **6/10**

Four compact documents: `spec/game_specification.md` (76 lines), `spec/architecture.md` (116), `spec/roadmap.md` (168, per-version Goal/Detailed Tasks/DoD/Tests — its best asset), `spec/web_ui_specification.md` (46). The architecture doc covers all the right headings, including a real Security & Isolation section (untrusted LLM, seat ownership, secret isolation) and a Testing Strategy naming mocked LLMs and contract tests — but at ~1,100 words it stays at bullet-point altitude: no wire-format schemas, no event payload tables, no identity/token lifecycle. Its §8 module layout (`server/games/`, `agent/llm/`, `designer/`, `web/`, tests split into `server/agent/e2e`, Docker files) **does not match what was built** (`games/` top-level, `client/`, `frontend/`, flat `tests/`, no Docker), and several spec promises (rehydration, `your_turn` events, tool calling, admin view, Dockerfiles) never shipped. Solid skeleton, weak on contracts, weak on enforcement.

## 4. SPEED (`code-generation-statistics.md`)

- **Total generation: 13 minutes 37 seconds** for all 15 phases (12:15:30–12:29:07 UTC+3), per-phase table included.
- Range: 30s (v05.03 swarm script) to 1m58s (v02.03 orchestrator/WS integration); most phases 37–63s.
- No token or velocity metrics. Claims "19 tests passed, MyPy 0 issues" — both contradicted at HEAD (see §2). Excludes the later manual debugging session (fix commit `79a2dc1`, ~9 incidents, 100 lines).

## 5. POST-GEN BUGS

- **`post-code-generation-errors.md`:** 9 incidents — 7 "business logic" (game state, WS payloads, routing; 24 files, 91 lines) + 2 "agent/infrastructure" (model-404, WS sync; 2 files, 9 lines). **Total: 26 files, 100 lines changed.** No per-bug severity or root cause; claims all resolved.
- **`errors.md`:** raw draft of the same session, **8** entries (3 "swarm start", 2 "server error", 3 "agent error") — count and taxonomy disagree with the formatted file; neither reconciles the other.
- Materially: ~16% of the 616-LOC codebase was rewritten post-generation, all bundled into one commit (`79a2dc1`) that also **introduced the test-suite regression** — the "all errors addressed" claim shipped alongside 8 newly failing tests.

## 6. SCORES

| Dimension | Score | Justification |
|---|---|---|
| **Code Quality** | **4/10** | Readable and compact, but DB layer dead, no `finally` cleanup, broken tests at HEAD, mypy-strict claims false. |
| **Architecture & Spec Adherence** | **4/10** | Game/LLM seams and server-side re-validation are real, but persistence, rehydration, tool-calling, seat-by-token, and the spec's own module layout are all unimplemented or contradicted (`first_move` breaks server authority outright). |
| **Testing Rigor** | **3/10** | 19 tests with one real WS E2E is respectable for 616 LOC, but 8 fail at HEAD, client/agent has zero coverage, and no DB-integration test. |
| **Security/Robustness** | **3/10** | Secrets correctly isolated to agent `.env` and moves fail closed, but unbound global tokens, client-mutable turn order, `innerHTML` XSS from LLM output, and broadcast fragility on dead sockets. |

**Bottom line:** a 13.5-minute build that looks complete on the surface (all 15 versions "released", polished README/UI) but is architecturally hollow underneath — persistence disconnected, identity model unenforced, and a final untested hot-fix that left the shipped HEAD with a 42% test failure rate. The 26-commit history (multi-issue commits, releases as tags only) makes none of this traceable per issue.
