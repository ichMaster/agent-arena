# Review: `origin/Gemini-3.1Pro-3.5Flash-dev` (spec: Gemini 3.1 Pro, code: Gemini 3.5 Flash)

## 1. INVENTORY

**Python source (818 LOC total):**
- `games/` — 86 LOC: `interface.py` (33), `tictactoe.py` (49), `__init__.py` (4)
- `server/` — 436 LOC: `main.py` (140), `websockets.py` (110), `repository.py` (69), `init_db.py` (45), `models.py` (43), `database.py` (29)
- `client/` — 296 LOC: `agent.py` (205), `llm.py` (60), `profile.py` (16), `memory.py` (14)

**Static web (784 LOC):** `static/app.js` (306), `styles.css` (395), `index.html` (83), plus `spectator_match.png` screenshot. Served at `/` (not `/ui`), no `Cache-Control` header.

**Tests:** 10 files, 673 LOC, **25 `def test_` functions** (test_server 9, test_tictactoe 7, test_repository 2, test_profile 2, five 1-test files) + `conftest.py` (real uvicorn server fixture on a free port).

**Config:** `requirements.txt` (13 deps), `mypy.ini` (`strict = True` + `ignore_missing_imports`), `VERSION` (05.03.00), `.gitignore`, 3 YAML profiles, `scripts/run_swarm.sh` (56 LOC). No pyproject, no Dockerfile (spec §7 promises docker-compose — never built).

**README:** 111 lines — good: structure tree, env setup, exact test/mypy commands, two run modes (swarm + human-vs-AI) with a screenshot. Accurate to the code.

## 2. CODE REVIEW

**(a) Architecture adherence**
- **Game seam:** present and honored — server touches rules only via `TicTacToe` in `MatchContext` (`server/websockets.py`). But signature diverged from spec: `apply_move(player, move) -> bool` and `is_game_over() -> Optional[str]` (winner string) vs spec's `apply_move(move)` / boolean.
- **LLM seam:** `client/llm.py` defines abstract `LLMClient`, but `client/agent.py` hardcodes `GeminiClient` — no factory, vendor not config-swappable; `model_type` in profiles only picks a Gemini model id. Seam exists on paper, not in wiring.
- **Server move authority:** yes — every `submit_move` goes through `game.apply_move` server-side; spectators rejected (`websockets.py process_action`); invalid moves get a per-client `{"error"}`. Solid.
- **Identity model — weakest point.** Tokens are minted at `/lobby/join` and mapped `match_id -> {token -> symbol}` (added post-gen, fix #6), but the WS handshake (`server/main.py websocket_endpoint`) only checks the token *is a UUID string* — it never verifies it was issued. Any self-minted UUID connects, then `ConnectionManager.connect` falls back to **connection-order** seat assignment ("Fallback for direct tests"). Also `JoinRequest.symbol` is client-asserted and unchecked for uniqueness — two clients can both claim "X"; "Spectator" role is inferred from the *player name* substring. Auth is format-theater.
- **Persistence gap:** `repo.log_move` / `update_match_status` are called **nowhere in the live server flow** (only `init_db.py` and tests — verified by grep). Moves are never persisted, match status never leaves PENDING, and the spec §4 crash-rehydration story is entirely unimplemented. Only chat is persisted. Live state is a mutable in-memory `TicTacToe`, deleted when the last socket drops.

**(b) Correctness**
- Engine (`games/tictactoe.py`): bounds/occupancy/turn checks all correct; 8 win vectors correct; draw detection correct (returns lowercase `"draw"` vs docstring's `"Draw"`). Nit: `isinstance(move, int)` accepts `True`/`False` as moves 1/0.
- Game-over: broadcast `game_over` then force-close all sockets (code 1000) — clean, tested end-to-end.
- WS cleanup: `manager.disconnect` in a `finally` block per spec; idempotent double-call. But malformed (non-JSON) frames aren't caught — `receive_json`'s `JSONDecodeError` escapes to `finally` and silently drops the client; `token_to_symbol` is never cleaned up (unbounded growth); `broadcast` swallows all exceptions bare.
- Agent (`client/agent.py`): derived-turn check (`current_turn == symbol`), 3-attempt retry with error-context re-prompt, 15s `asyncio.wait_for` timeout, random-legal fallback — matches the intended design well.

**(c) Typing:** two-tier. `games/` and `client/` are cleanly annotated and README only runs `mypy games/ client/` — because `server/` would not survive strict mypy: `token: str = None` (`main.py` WS endpoint), unannotated `serve_ui`/`lifespan`/pragma hook, legacy untyped `Column` models. The stats file's claim of "0 issues across all packages" is not credible for `server/`.

**(d) Testing:** 25 tests, all green per reports. LLM properly mocked (`test_agent.py` patches `GeminiClient` with `AsyncMock`; no paid calls anywhere). Real strengths: genuine integration tests over a live uvicorn + real `websockets` clients — full game to victory with both clients asserting every frame (`test_server.py::test_websocket_match_lifecycle`), concurrent 2-client chat broadcast, auth handshake rejection, FK-constraint test. Gaps: no test for spectator move rejection, none for the token→symbol map or slot-stealing (the very post-gen bug #6), no draw-over-WS, `GeminiClient` itself untested, several 1-test token files (`test_games.py` is 7 lines).

**(e) Security/robustness**
- Good: `GEMINI_API_KEY` stays in the client's `.env`, never sent to server; `.env`/`*.db` gitignored; Pydantic validates WS envelope; SQLAlchemy ORM (no SQL injection); FK pragma enforced.
- Bad: **XSS** — `static/app.js addChatMessage` injects `sender`/`text` via `innerHTML` for bot messages, so an LLM comment or spoofed sender containing HTML executes in every spectator's browser. Chat `sender` is client-supplied (spoofable). Unverified-token auth (above). `allow_origins=["*"]` with `allow_credentials=True`. No message length limits or rate limiting. Swarm script depends on `sleep`-based ordering.

## 3. SPEC QUALITY — 6/10

`spec/game_specification.md` (76 lines), `architecture.md` (116), `roadmap.md` (168), `web_ui_specification.md` (46). **Byte-identical to both `Gemini-3.1Pro-dev` and `Gemini-3.1Pro-3.1Pro-dev`** — `git diff ... -- spec/*.md --stat` is empty; pure shared lineage, zero divergence. It is a competent high-level spec: clear component split, a proper security section (untrusted LLM output, secret isolation, token-before-WS, Pydantic validation), an explicit testing strategy (mocked LLMs, contract tests), and a roadmap with per-version Goal/Tasks/DoD/Tests. But it is thin on contracts: no concrete WS payload schemas, no seat-uniqueness/identity rules (which is exactly where the implementation broke), an internal tension between §2.2's pull-style "tool use" and §2.6's push-event model, and §4 persistence/§7 Docker promises the build ignored. Score: **6/10** — sound skeleton, insufficient precision to constrain a weaker code generator.

## 4. SPEED (`code-generation-statistics.md`)

**Total: 35 minutes 26 seconds** across 15 phases (v01.01–v05.03), fully tabulated with per-phase start/end times. Fastest: v05.03 swarm script (41 s); slowest by far: v01.03 WebSocket ConnectionManager (14 m 44 s — 42% of the total); most phases ran ~45 s–2 m. Claims 25 tests passed and mypy strict clean (the latter overstated, see 2c).

## 5. POST-GEN BUGS (`post-code-generation-errors.md`)

**8 fixes** confirmed, all from live testing after generation "completed," each mapped to a commit: two module-path/PYTHONPATH failures (#1 swarm script, #8 direct CLI launch); two database failures (#2 missing tables on fresh launch → lifespan `create_all`; #4 FK violation on chat persist → auto-create match in `/lobby/join`, 53 lines); two WS lifecycle bugs (#3 `close()` on un-accepted socket → `WebSocketException`; #5 `RuntimeError` receiving on closed sockets); one game-integrity bug (#6 **spectators stealing the X seat** via connection order → token→symbol map, 48 lines across 4 files); one hang (#7 no LLM timeout → 15 s `asyncio.wait_for`). Severity: #2, #4, #6 were demo-blocking; #6 was a correctness/fairness bug in the core identity model. Net: the generated build failed its first real run in 8 distinct ways — heaviest post-gen fix load implied among documented sibling reports.

## 6. SCORES

- **Code Quality: 6/10** — clean small modules and a correct engine, but sloppy server typing, dead persistence code (`log_move` unused), and copy-paste session boilerplate in `main.py`.
- **Architecture & Spec Adherence: 5/10** — game seam and server authority honored; LLM seam not swappable, move-log/replay/status lifecycle unimplemented, identity by unverified token with connection-order fallback.
- **Testing Rigor: 6/10** — 25 tests with genuinely strong real-socket integration coverage and a properly mocked LLM, but thin unit files and no tests for the identity/spectator bugs it actually shipped.
- **Security/Robustness: 4/10** — correct secret isolation and server-side validation, undermined by format-only token auth, client-asserted symbols, chat sender spoofing, and a live `innerHTML` XSS in `static/app.js`.
