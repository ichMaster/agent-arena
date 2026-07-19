# Agent Arena — Post-Code-Generation Errors

**Scope:** 6 bugs found by actually *running* the generated software (human playing via the Web UI, the agent CLI against a real match, `scripts/run_swarm.sh`) — as opposed to `code-review-report.md`, which is a static review of the diff. Each entry below started as a terse one-line note in `bugs.md`; this document expands each into root cause, fix, and verification, and replaces `bugs.md` as the durable record.
**Method:** every bug was reported live (a pasted traceback, terminal output, or screenshot), reproduced from first principles (not guessed at), fixed, covered by a new regression test that was proven to fail without the fix and pass with it, then committed on its own.
**Status:** all 6 fixed and committed. Full suite is green after each fix (145 → 146 → 147 tests as bugs 5 and 6 each added one).

---

## Summary

| # | `bugs.md` note | Area | Root cause | Files changed | Lines | Commit(s) |
|---|---|---|---|---|---|---|
| 1 | "UUID issue" | Web UI | Match ID displayed truncated, then a browser-caching issue hid the fix | 5 | +61/-3 | `a7080fa`, `72ba041` |
| 2 | "agent issue — model name" | Agent/LLM | `GEMINI_MODEL` pointed at a non-existent model id | 6 | +15/-5 | `80fe061` |
| 3 | "swarm issue" | Agent CLI / swarm script | stdout block-buffered when redirected to a file | 2 | +69/-0 | `00b25ba` |
| 4 | "swarm issue — move logic" | Server / Web UI | No real spectator mode — "watching" a match claimed a player seat | 14 | +302/-32 | `007acfa` |
| 5 | "business logic issue" | Web UI | `isGameActive` flag never reset after a match ended | 2 | +19/-0 | `00bcbf1` |
| 6 | "agent issue" | Server | Winning move's `state_update` still claimed it was someone's turn | 4 | +43/-4 | `308c087` |

---

## 1. Match ID displayed truncated, then hidden by browser caching

**Reported as:** agent CLI `404 NOT_FOUND` on a match ID copied from the UI, then — after the first fix — a screenshot still showing the old truncated ID.
**Files:** `web/app.js`, `web/styles.css`, `server/main.py`, `tests/test_static_ui.py`

Two distinct bugs surfaced from the same user report:

**1a — truncation (`a7080fa`).** `web/app.js` displayed `matchId.slice(0, 8)` for cosmetic reasons, but that truncated string is exactly what the README tells users to copy into `client/agent.py --match-id ...` — an 8-char prefix isn't a valid match ID, so the agent's join request 404'd. Fixed with a `setMatchIdDisplay()` helper that renders the full ID (`word-break: break-all` added in CSS so it wraps instead of overflowing).

**1b — stale cache (`72ba041`).** After deploying the fix above, the user's browser kept showing the truncated ID. `curl -sI` confirmed the server *was* serving the corrected `app.js` — the browser was heuristically caching it, since Starlette's `StaticFiles` sets `ETag`/`Last-Modified` but no `Cache-Control`. Fixed with a `disable_ui_caching` middleware that sets `Cache-Control: no-store` on every `/ui/*` response.

**Tests:** `test_ui_app_js_displays_the_full_match_id_not_a_truncated_prefix`, `test_ui_assets_are_never_cached_by_the_browser`, `test_non_ui_routes_are_unaffected_by_the_no_store_header`.

---

## 2. `GEMINI_MODEL` pointed at a model id that doesn't exist

**Reported as:** `google.genai.errors.ClientError: 404 NOT_FOUND. {'error': {'message': 'models/gemini-3.1-pro is not found for API version v1beta...'}}` from a real agent run.
**Files:** `client/llm.py`, `profiles/aggressive_bot.yml`, `profiles/cowardly_bot.yml`, `tests/test_agent.py`, `tests/test_llm.py`, `tests/test_profile.py`
**Commit:** `80fe061`

`"gemini-3.1-pro"` was never a real model id. Confirmed the real one via a live (free, metadata-only) `client.aio.models.list()` call — never the paid `generate_content()` call — which returned `gemini-3.1-pro-preview`. Updated the `GEMINI_MODEL` constant and both sample profiles; `tests/test_llm.py` gained an assertion pinning the constant so this can't silently drift again.

---

## 3. Agent stdout not flushed when redirected to a file

**Reported as:** `scripts/run_swarm.sh` timing out with `ERROR: Aggressor-Prime did not connect within 50 attempts` even though the agent had, in fact, connected.
**Files:** `client/agent.py`, `tests/test_agent.py`
**Commit:** `00b25ba`

Python block-buffers stdout by default when it's redirected to a file/pipe (not a TTY) — the swarm script redirects each agent's output with `>log 2>&1`. The "Joined as 'O'..." line the wait-loop `grep`s for sat unflushed in memory. Fixed with `sys.stdout.reconfigure(line_buffering=True)` / same for stderr in `main()`. Verified the new subprocess-based regression test actually catches this: reverted the fix via `git stash`, confirmed the test failed, restored it, confirmed it passed.

---

## 4. No real spectator mode — "watching" a match stole a player's seat

**Reported as:** a full swarm run where `Aggressor-Prime` ended up assigned `'O'` and `Nervous-Nelly` got `symbol: None` — "nothing happens, nobody makes a first move."
**Files:** `server/match.py`, `server/websockets.py`, `server/main.py`, `server/auth.py`, `server/schemas.py`, `web/app.js`, `web/index.html`, `scripts/run_swarm.sh`, plus `tests/test_match.py`, `tests/test_server.py`, `tests/test_static_ui.py`, `tests/test_swarm_script.py`, and `README.md`
**Commit:** `007acfa`

Root cause: the swarm script told users to watch a match by clicking **Join Match** — which claims a real player seat server-side. A human spectating in the browser silently took the seat meant for the second scripted agent, so only one of the two agents ever had a symbol. Fixed by implementing a genuine spectator path end to end: `POST /lobby/join` accepts a `spectator` flag → `IssuedToken.is_spectator` → `Match.mark_spectator()` permanently refuses that participant a seat (idempotent even if they already hold a seat) → a dedicated **Spectate Match** button in the Web UI that never calls the player-claiming join flow. Also fixed a related crash: `initPlayerCards(null)` — a spectator's `joined` event carries `symbol: null` — used to throw on `null.toLowerCase()`.

---

## 5. `isGameActive` never reset after a match ended

**Reported as:** "I've created a new match as a player and cannot make a new move."
**Files:** `web/app.js`, `tests/test_static_ui.py`
**Commit:** `00bcbf1`

`handleGameOver()` sets `isGameActive = false` when a match ends but nothing ever set it back to `true`. Hosting or joining a *second* match in the same browser tab (no full page reload) left the flag permanently `false`: `renderBoard`'s `isMyTurn` calculation and `handleCellClick`'s early-return both gate on it, so every cell rendered disabled and clicks silently no-op'd — a brand-new match could be created but never played. Verified server-side logic was never the problem first, via a live WebSocket reproduction script exercising both a solo host and a full two-player move sequence end to end. Fixed by resetting `isGameActive = true` at the top of `promptAndJoin()`, the common entry point for host/join/spectate.

---

## 6. Winning move's `state_update` still claimed it was someone's turn

**Reported as:** an agent crash — `websockets.exceptions.ConnectionClosedOK: received 1000 (OK); then sent 1000 (OK)` — immediately after the agent printed its winning move's chat comment.
**Files:** `server/websockets.py`, `spec/architecture.md`, `README.md`, `tests/test_websockets.py`
**Commit:** `308c087`

`Match.current_turn` only tracks move parity; it has no idea a given move just ended the game. The winning move's own `state_update` broadcast therefore still reported the next parity symbol (e.g. `"O"`) as `current_turn`. `client/agent.py`'s `AgentSession.is_my_turn` treats a `state_update` where `current_turn == my_symbol` as "act now" — so on the exact move that ended the game, the agent decided another move and tried to send chat into a room the server had, by then, already closed via the immediately-following `game_over` broadcast. Fixed by computing `is_game_over()` *before* building the `state_update` payload and reporting `current_turn: null` whenever the move that was just applied ends the game — a semantically correct value ("no one's turn is next"), not a client-side patch, so it protects the Web UI the same way. Updated `spec/architecture.md` and the README's WS protocol table per the project's rule that any change to a stable WS payload shape must be documented in the same commit.

---

## Pattern across all six

These were all **live-usage bugs** — only catchable by actually running the software (playing a match, launching the swarm script, watching a real agent traceback), not by reading a diff. They cluster into two recurring shapes:

- **Stale/orphaned client-side flags** (#1a, #1b, #5): state that's set once and never reset for the next match/session in the same tab.
- **The server telling the truth about the wrong moment** (#4, #6): a value (`symbol: null`-eligibility, `current_turn`) that's technically correct by one definition but misleading at the exact instant a client reads it, because game-over/spectator status wasn't consulted before computing it.

Bug #2 and #3 are unrelated one-offs (a wrong external API id; a stdlib buffering default).
