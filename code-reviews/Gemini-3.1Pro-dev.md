# Review: `origin/Gemini-3.1Pro-dev` (Gemini 3.1 Pro, interactive build)

## 1. INVENTORY

**Python source (720 LOC total):**
- `games/`: 101 LOC — `interface.py` (35), `tictactoe.py` (66), `__init__.py` (0)
- `server/`: 336 LOC — `main.py` (96), `websockets.py` (104), `models.py` (41), `repository.py` (44), `init_db.py` (26), `database.py` (24), `__init__.py` (1)
- `client/`: 283 LOC — `agent.py` (199), `llm.py` (58), `profile.py` (26)

**Web (744 LOC):** `web/app.js` (289), `web/styles.css` (362), `web/index.html` (93). Plus `css_guide.md` (530 lines) at root.

**Tests:** 8 files, 481 LOC, **21 `def test_` functions** — `test_server.py` (8), `test_tictactoe.py` (6), `test_repository.py` (2), 1 each in `test_database/games/models/websockets/match_lifecycle`.

**Config:** `requirements.txt` (15 unpinned deps except `PyYAML==6.0.1`; includes suspicious **`httpx2`** — likely a typo for `httpx`, which `TestClient` actually needs), `mypy.ini`, `VERSION` (05.03.00), `RELEASE.txt`, `.gitignore` (solid). No pyproject, no CI.

**README:** 110 lines, good — features, curl examples, WS/UI/agent/swarm walkthroughs.

**Repo hygiene — poor at root:** `agent_out.txt` (pasted agent session log), `match.txt` (a single match UUID), `test_client.html` (superseded manual test page), `css_guide.md` all committed to root; commit `46c4c05` is literally "chore: push all untracked files as requested". These are workspace debris, not deliverables.

## 2. CODE REVIEW

**(a) Architecture adherence**
- `GameInterface` seam (`games/interface.py`) is clean; `TicTacToe` implements it; `websockets.py` only calls the interface. Good. Deviation: `apply_move(player, move) -> bool` (spec has no `player` arg) and `is_game_over()` doubles as winner-getter.
- `LLMClient` ABC exists in `client/llm.py` with `GeminiClient`, but `agent.py` **hard-instantiates `GeminiClient`** — no factory/config switch, so the vendor seam is nominal.
- Server-side move authority: **yes** — every move re-validated via `apply_move` in `ConnectionManager.process_action` (`server/websockets.py`).
- **Identity model fails the spec.** Seats are assigned by **connection order**, keyed by WebSocket object (`MatchContext.add_player`: 1st=X, 2nd=O, rest Spectator). The token from `/api/v1/lobby/join` is a random UUID **never stored or checked against anything** — any well-formed UUID passes (`server/main.py`). Consequences: (1) any early connector (e.g. a spectator) **steals a player seat** — "fixed" only by docs ordering in `run_swarm.sh` (commit `e8976cb`); (2) if X drops and reconnects while O remains, the rejoiner is assigned **'O' — two O seats**; (3) reconnection/seat recovery impossible. No `participants` table, no `UNIQUE(match_id, symbol)`.
- **No persistence of moves/state.** Live game lives only in `MatchContext.game` (memory); `repository.log_move` exists but is **never called** in the live path — no replay-from-move-log, `MatchModel.status` stays PENDING forever. Chat is the only thing persisted. Server restart loses all games. 3 tables vs the spec's 4.

**(b) Correctness**
- Engine (`games/tictactoe.py`): correct — type/bounds/occupancy/turn checks, all 8 win lines, draw.
- **Web UI hardcodes the human as X** (`app.js` `handleCellClick`: `if (currentTurn !== 'X') return; // Human is X`). The README's two-tab human-vs-human flow cannot work: tab 2 holds seat O server-side but its UI only unlocks cells on X's turn, and any click is rejected as O-out-of-turn. Role is client-asserted, contradicting "roles decided server-side".
- **Stale failing test at HEAD:** fix `636eb9e` changed `get_state()["status"]` from `None` to `"ACTIVE"` but `tests/test_tictactoe.py::test_initial_state` still asserts `state["status"] is None` — the suite fails on the branch tip.
- WS cleanup: `main.py` handles `WebSocketDisconnect` + a string-matched `RuntimeError`, but **no `finally`** — an async cancellation path leaks the seat. On game over the server force-closes all sockets (code 1000), which is tidy in tests but kills post-game chat.
- Agent: derives turn correctly (`turn == symbol and status == "ACTIVE"`), 3-retry-then-random-legal fallback implemented (`client/agent.py`) — matches spec. But the symbol is a **CLI argument**, not server-assigned; a mislabeled agent silently never moves.

**(c) Typing** — Partial. `games/` and `server/websockets.py` are annotated; `client/agent.py` is largely untyped (`MemoryWindow.__init__(self, limit=10)`, `run_agent` untyped params), `server/main.py` handlers untyped, `token: str = None` is a type error. `mypy.ini` sets `disallow_untyped_defs = True` globally, so mypy over the whole repo would fail; in practice only `games/` was gated (ARENA-013).

**(d) Testing** — 21 tests. Engine coverage is genuinely good (parametrized all 8 win vectors, draw, invalid moves). `test_match_lifecycle.py` is a strong 3-client E2E (spectator rejection, out-of-turn rejection, win, graceful close). Repository/FK tests present. **Zero tests for `client/`** — LLM, profile parsing, retry/fallback all untested (no mock exists; the only `LLMClient` exercise is a live-API `_test()` in `llm.py`). No contract test on the WS schema. "LLM mocked in tests" holds only vacuously.

**(e) Security/robustness**
- **XSS:** `renderChat` in `web/app.js` injects `data.sender`/`data.message` via `innerHTML` — any peer or agent chat message executes HTML/JS in other clients. Chat is also persisted, so it's stored XSS.
- **Auth is decorative:** token = any client-supplied UUID; `sender` in chat is client-asserted (spoofable), never bound to the connection.
- Secrets: correct — `GEMINI_API_KEY` only in the agent's `.env`, gitignored, never sent to server.
- CORS `allow_origins=["*"]` with `allow_credentials=True`; unbounded chat message length; `MatchContext` created for any UUID-shaped `match_id` (memory-growth vector, no DB existence check on WS connect).

**Strengths:** clean small engine + interface seam; real server-side validation; good E2E lifecycle test; working retry-then-random-fallback agent; profiles-as-YAML (`profiles/*.yml`, `client/profile.py`) delivered; swarm orchestrator (`scripts/run_swarm.sh`); consistent release discipline (15 tagged releases, RELEASE.txt).

## 3. SPEC QUALITY

`spec/game_specification.md` (76 lines / 833 words) and `spec/architecture.md` (116 / 1083) are well-structured but thin — headline-level bullets rather than contracts. Architecture does name the right ideas (server as ultimate authority, untrusted LLM output, secret isolation in agent `.env`, mocked-LLM CI, contract tests, a module tree with `tests/{server,agent,e2e}`), plus `spec/roadmap.md` (168 lines, 15 phases) and a short `web_ui_specification.md`. But there are no wire-payload schemas, no identity/seat model, no DB schema, and the implementation visibly diverged from even this spec (token auth, move-log persistence, test layout all unrealized). Post-hoc `docs/architecture.md`/`code_explanation.md` describe what was built, not what was promised. **Score: 6/10.**

## 4. SPEED

From `git log --date=iso`: first implementation commit `968b51f` (ARENA-001) **2026-07-17 21:35:26 +0300** → final release `e70eeb7` (Release v05.03.00) **2026-07-18 02:32:07 +0300**.
- **Elapsed wall-clock: ~4 h 57 m** (~4 h 59 m to the last docs commit `f7f14e1` 02:34).
- **89 commits** in that window (96 total on branch).
- **15 releases**: v01.01.00 → v05.03.00, all phases of the roadmap shipped, evenly paced (~20 min/version).

## 5. POST-GEN BUGS

No `post-code-generation-errors.md`. `git log -i --grep fix` shows **5 dedicated fix commits**, plus 2 fixes folded into `b684606` per v05.02.00 release notes (chat-sender identity bug, unsupported model versions):
- `1360982` tests didn't account for initial `state_update` broadcast (low)
- `2fca319` wrong Gemini model id (low, config)
- `8a1ad82` agent kept moving after game over (medium, logic)
- `636eb9e` status reported `null` instead of ACTIVE — broke UI reactivity (medium; **left a stale failing test behind**)
- `e8976cb` spectators stealing player slots — patched via **docs/launch-order only**, root cause (connection-order seating) never fixed (high, unresolved in code)

Low fix count overall, consistent with interactive manual testing per version; the seat-stealing and two-tab-play defects survived to HEAD.

## 6. SCORES

- **Code Quality: 6/10** — small, readable, cohesive modules, but untyped client code, dead repository methods, a failing test at HEAD, and root-level debris.
- **Architecture & Spec Adherence: 4/10** — GameInterface and server authority honored, but token identity is fake, seats are connection-order, no move persistence/replay, LLM seam not config-switchable, UI role client-asserted.
- **Testing Rigor: 5/10** — solid engine + one strong E2E, but zero client/LLM tests, no mocks, no contract tests, and the suite is red at branch tip.
- **Security/Robustness: 3/10** — stored XSS via `innerHTML` chat, decorative auth, spoofable sender, seat hijack, `CORS *` + credentials; only secret isolation is done right.
