# Review: `origin/Anthropic-Gemini3.1Pro-Sonet5-dev` (spec: Gemini 3.1 Pro, code: Sonnet 5)

## 1. INVENTORY

**Python source — 1,005 LOC / 20 files** (3 empty `__init__.py`):
- `games/` (56): `interface.py` 20, `tictactoe.py` 36
- `server/` (572): `websockets.py` 172, `main.py` 126, `match.py` 73, `models.py` 53, `repository.py` 44, `database.py` 34, `init_db.py` 28, `auth.py` 25, `schemas.py` 17
- `client/` (377): `agent.py` 260, `llm.py` 55, `memory.py` 19, `profile.py`/`prompt.py` 18/19, `schemas.py` 6

**Web — 684 LOC**: `web/app.js` 224, `web/styles.css` 388, `web/index.html` 72.
**Tests — 15 files + conftest, ~1,793 LOC, 130 `def test_` functions** (test:source LOC ratio ≈ 1.8:1). Largest: `test_agent.py` 33 tests/581 LOC, `test_server.py` 19/343, `test_websockets.py` 17/282. Reports claim 147 passing at final state.
**Config**: `requirements.txt` (13 pins), `requirements-dev.txt`, `mypy.ini`, `pyproject.toml` (pytest config only — no `[project]`/build-system; not pip-installable), `VERSION`, `RELEASE.txt`, 2 `profiles/*.yml`, `scripts/run_swarm.sh`. No `.env.example`.
**README** (117 lines): excellent — architecture, full WS protocol table, setup, three run modes, honest "Known limitations" section, testing commands. Among the best README artifacts I'd expect from this exercise.

## 2. CODE REVIEW

**(a) Architecture adherence — strong.** `games/interface.py` is a clean ABC; `apply_move(player, move) -> bool` never raises, is the sole legality authority. `client/llm.py` `LLMClient` ABC + `create_llm_client()` factory is the only vendor mapping point (only `GeminiClient` exists; non-Gemini `model_type` raises). Server authority is real: `server/websockets.py:_handle_submit_move` re-derives the sender's symbol from its seat (token), checks `match.current_turn != symbol`, then `game.apply_move()` — client claims are never trusted. Seats keyed by per-connection auth token (`server/main.py` passes `participant_id=token`; `server/match.py` documents why name-keying was wrong). Spectators are marked server-side and permanently refused a seat (`Match.mark_spectator`), decided by the `spectator` flag at `/lobby/join` — never client-asserted at the WS layer. Deviation from spec: `spec/architecture.md` §4 promises "Stateless Server Recovery" (rehydrate matches from DB on boot); the implementation logs moves but **never replays them** — `Match` lives only in `_active_matches` RAM, so a server restart silently loses live games.

**(b) Correctness — good, with nits.** Move validation covers type/bounds/occupancy; turn is parity-derived; `is_game_over()` correct over all 8 lines + draw. Subtle right calls: `current_turn: null` on the game-ending `state_update` (spec-updated in the same commit); WS cleanup in a `finally` block in `server/main.py` with an accurate explanation of the anyio `CancelledError`-not-`WebSocketDisconnect` trap; `broadcast()` per-socket try/except removes only the failed socket. Nits: `isinstance(move, int)` in `tictactoe.py` accepts `bool` (`{"move": true}` plays cell 1); `release_seat` on disconnect means any newcomer can inherit a mid-game seat (a takeover window, though it un-strands matches); `joined` is sent only to self, so peers never learn a player arrived; one DB session is held for the entire WS connection lifetime.

**(c) Typing — the weakest area.** `mypy.ini` sets `strict = True` **only for `games.*`** (56 LOC); `server/` and `client/` get default (lenient) checking, and `tests.*` has `ignore_errors = True`. README documents only `mypy games/`. Hints are present and mostly complete across all modules (incl. one honest `type: ignore[union-attr]` for a typeshed gap), but enforcement is a fraction of the codebase.

**(d) Testing — a highlight.** 130 test functions. LLM always mocked (`google.genai.Client` patched in `tests/test_llm.py`/`test_agent.py`; the one live call ever made was a free `ListModels`, documented). Real integration: `test_server.py:test_ws_two_players_complete_full_tictactoe_game` plays a full game over TestClient WS, plus name-collision, seat-reclaim-on-disconnect, spectator-cannot-move, malformed-JSON tests; `test_agent.py` runs **real uvicorn on a thread** (`live_server` fixture) and completes full games over genuine `websockets` connections, plus a subprocess test that `python client/agent.py` runs as a direct script. Regression tests were proven-to-fail-then-pass (documented per bug). Gap: Web UI verified only by static-content assertions (`test_static_ui.py`), no browser automation — acknowledged.

**(e) Security/robustness — mixed.** Good: Pydantic validation of every WS payload; token required before `accept()` (close 4001), token bound to match_id; `GEMINI_API_KEY` only in the client's `.env` with fail-fast; Web UI uses `textContent`/`createTextNode` (no innerHTML → XSS-safe); malformed JSON answered with an error, not a crash; agent survives unparseable/hallucinated LLM output (3 retries → random legal fallback). Weak: tokens in URL query strings (log leakage), in-memory with no expiry (`server/auth.py`); CORS `allow_origins=["*"]` **with** `allow_credentials=True` (`server/main.py`); unbounded chat message length; no rate limiting; the disconnect seat-takeover window above. Flag: dependency **`httpx2==2.7.0`** (`requirements.txt`, imported throughout `client/agent.py`/tests) — not the canonical `httpx` package name; provenance worth verifying.

## 3. SPEC QUALITY (Gemini 3.1 Pro-authored)

Notably **thin** next to the Opus spec on sibling branches: `game_specification.md` 76 lines, `architecture.md` 121, `roadmap.md` 168, `web_ui_specification.md` 46. Structure is clean (arch covers components, security, testing, deployment, project tree; roadmap has 15 sub-versions each with Goal/Tasks/DoD/Tests and arch cross-refs), and it does name the right invariants (untrusted LLM, token-not-name identity, mocked LLMs, secret isolation). But it lacks concrete wire schemas, error codes, and DDL; it originally specified a pull-style "Agent Tools" model (`get_game_status`, `connect_to_server`) and a `your_turn` event that the implementation replaced with push + structured JSON — the arch doc had to be retro-amended (per code-review finding #7); its §8 project tree (`server/games/`, `agent/`, `designer/`) never matched the built layout (`games/`, `client/`); and §4's crash-rehydration promise went unimplemented. A workable sketch that left the builder to invent the actual contracts. **Score: 6/10.**

## 4. SPEED (`spec/implementation/execution-time-report.md`)

- **Roadmap build: 58m 57s** (34 issues, 64 commits, 113 tests, 26 source + 14 test files; sum of phase durations 53m 51s + ~5m overhead). 5/5 phases, 15/15 releases.
- Per phase: P1 10m 46s, P2 6m 33s, P3 17m 07s (slowest; agent), P4 10m 58s, P5 8m 27s. Fastest sub-version 1m 08s (v02.01), slowest 7m 25s (v03.01).
- **Post-review fix pass: 16m 43s** (12/12 findings, 5 commits, tests 113 → 132). **Combined active implementation: 1h 15m 40s**; total wall-clock span first-to-last commit 3h 10m 13s (the ~1h 55m gap was the 8-finder/12-verifier code review itself). 6 bugs found and fixed mid-run.

## 5. POST-GEN BUGS

**`post-code-generation-errors.md`: 6 live-usage bugs, all fixed + regression-tested (145 → 147 tests).** By area: Web UI 3 (#1 truncated match-ID display + browser caching; #5 `isGameActive` never reset — new match unplayable without reload), Server 2 (#4 **no real spectator mode** — watching stole a player seat, 14 files/+302 lines, the biggest fix; #6 winning move's `state_update` claimed it was still someone's turn → agent crash `ConnectionClosedOK`), Agent 2 (#2 nonexistent model id `gemini-3.1-pro` → 404; #3 stdout block-buffering broke the swarm script). Severity: #4/#6 gameplay-breaking for agent-vs-agent, #1/#5 UX-breaking, #2/#3 config/environment. The report's own pattern analysis (stale client flags; "server telling the truth about the wrong moment") is unusually good.

**`code-review-report.md` (in-pipeline): 12 findings, 12/12 independently confirmed, 0 refuted** — 2 Critical (seats keyed by player name; no seat reclaim on disconnect), 2 High (`/lobby/join` no match-existence check; `broadcast()` disconnects the wrong socket), 3 Medium, 5 Low. All 12 fixed in the 16m 43s pass, plus a 13th bug found en route (the `CancelledError` disconnect-cleanup trap). Notably, both Critical findings were in the seat/identity model the CLAUDE.md non-negotiables warn about — introduced first, caught by review, not by the initial build.

## 6. SCORES

| Dimension | Score | Justification |
|---|---|---|
| Code Quality | 8/10 | Compact (~1k LOC), exceptionally well-commented with *why*-rationale at every tricky spot; docked for `games`-only mypy strictness, non-installable `pyproject.toml`, and the odd `httpx2` dependency. |
| Architecture & Spec Adherence | 8/10 | Both seams clean, true server authority, token-keyed seats, seam changes doc'd in-commit; docked for unimplemented DB rehydration (spec §4) and spec-tree/tool-model drift. |
| Testing Rigor | 9/10 | 130 tests at 1.8:1 test:source LOC, LLM always mocked, full games over both TestClient WS and a real uvicorn server, proven-to-fail regression tests; only gap is no browser-level UI testing. |
| Security/Robustness | 6/10 | Validates everything inbound, XSS-safe DOM, secrets isolated, hallucination fallback; but query-string tokens without expiry, `CORS *` + credentials, seat-takeover-after-disconnect, no rate/size limits. |
