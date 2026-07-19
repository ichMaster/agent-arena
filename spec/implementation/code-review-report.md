# Agent Arena — Code Review Report

**Scope:** full diff `main...HEAD` (64 files, ~3600 insertions — the entire implementation produced by `/execute-all-phases`).
**Method:** `code-review` skill, high effort. 8 independent finder angles (3 correctness, 3 cleanup, 1 altitude, 1 conventions-vs-`CLAUDE.md`) run in parallel, each surfacing up to 6 candidates. 12 candidates survived dedup; every one was independently verified by a second agent given only the candidate claim and the real code (not the finder's reasoning). **All 12 verified CONFIRMED — none refuted.** The 10 most severe are reported below; 2 minor efficiency findings (redundant JSON serialization in `ConnectionManager.broadcast`, and `build_prompt` being invoked twice with identical arguments in the move-retry loop) were dropped only because correctness/conventions findings outrank cleanup ones when a cap forces a cut — not because they were weak.
**Status:** none of these are fixed yet. This document is a record of the review; see `README.md`'s "Known limitations" section for the user-facing summary.

---

## Prioritization

Criticality = severity/likelihood of real harm if left unfixed. Effort = size to fix, using this repo's own `S`/`M`/`L` convention from `spec/implementation/*-issues.md` (`S` = quick/contained, `M` = touches a few call sites or needs a small design decision, `L` = multi-file redesign). Sorted by recommended fix order — criticality first, effort as the tiebreaker.

| Order | # | Finding | Criticality | Effort | Quadrant |
|---|---|---|---|---|---|
| 1 | 2 | No seat reclaim on disconnect | Critical | S | **Do first** |
| 2 | 1 | Seat identity by player name (default-name collision) | Critical | M | **Do first** |
| 3 | 3 | `/lobby/join` doesn't validate match exists | High | S | **Do first** |
| 4 | 4 | `broadcast()` disconnects the wrong player | High | S | **Do first** |
| 5 | 6 | Swarm script `--symbol` race | Medium | M | Do next |
| 6 | 8 | LLM vendor not swappable via config | Medium | S | Quick win |
| 7 | 5 | `generate_structured_response` return type not narrowed | Medium | S | Quick win |
| 8 | 7 | `architecture.md` missing the `joined` event | Low | S | Quick win |
| 9 | 9 | `CLAUDE.md` structure doesn't match reality | Low | S | Quick win |
| 10 | 10 | Unnecessary DB `refresh()` per message | Low | S | Quick win |
| — | 11* | `broadcast()` re-serializes JSON per recipient | Low | S | Quick win |
| — | 12* | `build_prompt` double-invocation in retry loop | Low | S | Quick win |

*Dropped from the top-10 in the original report (cap, not weakness) — included here since they're both trivial to fix.

**Reading this table:**
- **Do first (1–4):** the two critical findings are both cheap-to-medium to fix and directly cause silent data corruption (#1, shared seats) or a permanent stuck state (#2, no reclaim) in the *default* usage path — highest return on effort in the whole set. #3 and #4 are one-function fixes that close real crash/mis-disconnect bugs.
- **Do next (5):** the swarm race is real but lower-stakes (mislabels which persona plays which side; doesn't corrupt gameplay) and the clean fix (server accepts a requested symbol at join, or the script waits for a connection-confirmed handshake before launching the second agent) is a genuine small design decision, not a one-liner — hence `M` despite `Medium` criticality.
- **Quick wins (6–12):** every one of these is `S` effort — a few lines each (a `TypeVar`, a doc paragraph, a two-line dispatch, deleting a redundant `refresh()` call, moving a `model_dump()` outside a loop). There's no reason to defer any of them; the only reason they rank below 1–4 is lower criticality, not cost.
- **Notably absent:** no finding in this review is `L` effort. The codebase's issues are all real but all cheap — a single focused pass could plausibly clear the entire list.

---

## 1. Seats are identified by player name, not connection — default names collide

**File:** `server/match.py:16` (`Match.assign_symbol`)
**Category:** correctness · **Severity:** critical (hits the default UX path)

`assign_symbol` keys a game seat by the raw `player_name` string. `web/app.js`'s join prompt defaults every session to the literal name `"Human"` (`window.prompt('Enter your name:', 'Human')`). Two different people who both accept that default and join the same match both resolve to `assign_symbol("Human")`: the second call hits the early-return branch (`if player_name in self.player_symbols: return self.player_symbols[player_name]`) and silently gets back the *same* symbol already assigned to the first. Both connections can now submit moves as that symbol interchangeably, with no error, and their chat messages render as indistinguishable in the UI (`renderChat` compares `sender === myPlayerName`).

This is not an edge case — it's the default behavior of the primary human-vs-agent (or human-vs-human) flow.

---

## 2. A mid-game disconnect permanently strands the match

**File:** `server/match.py:16` (`Match.player_symbols`, no removal path) / `server/main.py:89-90`
**Category:** correctness · **Severity:** critical

`server/main.py`'s `except WebSocketDisconnect` handler only calls `ConnectionManager.disconnect` (removes the socket from the connection list) — it never touches `Match.player_symbols`. The only thing that clears a match's seats is `clear_match`, called solely on `game_over`. If the X (or O) player's connection drops mid-game (crash, closed tab, network drop), `assign_symbol` for any new `player_name` returns `None` once two seats are taken — there is no reclaim, timeout, or eviction path. The match is permanently stuck with one live player, recoverable only by restarting the entire server process, which also drops every other concurrent match.

---

## 3. `POST /api/v1/lobby/join` doesn't check the match exists — crashes on first message

**File:** `server/main.py:52`
**Category:** correctness · **Severity:** high

`join_match` only calls `auth.issue_token(...)` — no `Repository.create_match` call, no DB lookup at all. `MoveLogModel.match_id`/`ChatLogModel.match_id` are `ForeignKey("matches.id")`, and `Repository.log_chat`/`log_move` `INSERT` with no surrounding `try/except`. With `PRAGMA foreign_keys=ON` enabled, a client that joins with a `match_id` that was never created via `POST /api/v1/lobby/match` (e.g. a typo'd `--match-id` passed to the agent CLI, or any direct API caller) connects successfully but crashes the WebSocket connection with an uncaught `sqlalchemy.exc.IntegrityError` on its first chat or move.

---

## 4. `ConnectionManager.broadcast` disconnects the wrong player on a dead socket

**File:** `server/websockets.py:38-40`
**Category:** correctness · **Severity:** high

`broadcast` loops over every socket in the room and calls `await websocket.send_json(...)` with no per-socket `try/except`. If one socket is stale (browser closed, network dropped, but the server hasn't yet processed a clean disconnect), `send_json` raises `WebSocketDisconnect(1006)` (starlette translates the underlying `OSError`), which propagates unguarded up through `_handle_submit_move`/`handle_client_message` into `match_socket`'s loop. The outer `except WebSocketDisconnect: manager.disconnect(match_id, websocket)` then disconnects the **current** connection — the live player whose message triggered the broadcast — not the socket that actually failed. The genuinely dead entry stays registered, permanently breaking future broadcasts to that room.

---

## 5. `generate_structured_response`'s return type isn't narrowed to the caller's schema

**File:** `client/llm.py:16`
**Category:** correctness (type-safety) · **Severity:** moderate

`LLMClient.generate_structured_response(self, prompt: str, schema: type[BaseModel]) -> BaseModel` returns the generic `BaseModel`, not a type tied to `schema` (e.g. via a `TypeVar` bound to `BaseModel`). `client/agent.py`'s `_decide_move` calls this with `AgentResponse` and immediately accesses `.move`/`.comment` on the result with no cast. Running `mypy client/ server/ --config-file mypy.ini` reproduces exactly the predicted errors: `"BaseModel" has no attribute "move"` / `"comment"` at `client/agent.py:154,158,160,163`, plus an incompatible-return-type error at `:155`. The type checker has no way to catch a real attribute typo here.

---

## 6. The swarm script's X/O assignment is a race, not a guarantee

**File:** `scripts/run_swarm.sh:34-47` / `client/agent.py:174-182`
**Category:** correctness / altitude · **Severity:** moderate

`run_swarm.sh` backgrounds `python client/agent.py --symbol X --profile aggressive_bot.yml` and `--symbol O --profile cowardly_bot.yml` back-to-back with `&`, with no lock or ordering guarantee between them. `server/match.py`'s `assign_symbol` takes no symbol parameter at all — it's purely first-connected-gets-X. Whichever process's async HTTP join + WS connect completes first (a race on process scheduling/network timing) actually gets X, regardless of `--symbol`. The only mitigation is a `stderr` `WARNING` printed by `client/agent.py` on mismatch, buried in a log file the script only tails after the fact — the aggressive persona could end up controlling O with nothing in the script's own printed narrative indicating it.

---

## 7. `spec/architecture.md` doesn't document the real WebSocket protocol

**File:** `spec/architecture.md:17,58`
**Category:** conventions (`CLAUDE.md`) · **Severity:** moderate

`CLAUDE.md` states verbatim: *"Any change to a stable seam (WebSocket JSON payload schema, `GameInterface`, `LLMClient` interface) must update `spec/architecture.md` and its contract test in the same commit."* `server/websockets.py`'s `send_joined_event` sends a genuine new push event (`joined`) once per accepted connection, but `spec/architecture.md` never mentions it and still documents a `your_turn` event as the turn-notification mechanism — and `your_turn` has zero occurrences anywhere in the actual server/client code. The doc was already stale before this change; the new seam compounded rather than fixed it.

---

## 8. LLM vendor isn't actually swappable via profile config

**File:** `client/agent.py:231`
**Category:** conventions (`CLAUDE.md`) · **Severity:** moderate

`CLAUDE.md` states verbatim: *"`LLMClient` is the only way an agent talks to a model vendor. ... vendor clients are swapped via config, never referenced directly from agent/parsing code."* `AgentProfile.model_type` exists as a field precisely to drive this choice, but it's never read anywhere in `client/agent.py` — `run()` directly imports and hardcodes `GeminiClient(api_key=api_key, temperature=profile.temperature)`. Switching a profile to a different vendor currently requires editing application code, not just its YAML.

---

## 9. `CLAUDE.md`'s documented project structure doesn't match reality

**File:** `CLAUDE.md:56-66`
**Category:** conventions / documentation drift · **Severity:** low-moderate

`CLAUDE.md`'s "Project structure (target, once implemented)" section documents top-level `agent/` (WebSocket client loop, tool-call parser, `llm/`) and `designer/` (Agent Profile schemas + generator) directories. Neither exists as implemented — `agent/` was never created, `designer/` is an empty leftover, and every one of those files (`agent.py`, `llm.py`, `profile.py`, `prompt.py`, `memory.py`, `schemas.py`) lives under `client/` instead, per how the actual implementation issues were scoped. A future contributor or agent trusting `CLAUDE.md`'s structure section will look in the wrong place.

---

## 10. Unnecessary DB `refresh()` on every chat/move message

**File:** `server/repository.py:27,40`
**Category:** efficiency · **Severity:** low

`Repository.log_move` and `log_chat` both call `await self._session.refresh(...)` after `commit()`, issuing an extra `SELECT` round trip. Every call site (`server/websockets.py`'s `_handle_submit_move` and `handle_client_message`) discards the return value entirely — the refresh result is never read. This is an avoidable DB round trip on the hot path of every single move and chat message in every match.

---

## Findings dropped for the cap (still confirmed, just lower severity)

- **`ConnectionManager.broadcast`** (`server/websockets.py:39`) calls `event.model_dump()` inside the per-recipient loop instead of once before it — redundant serialization for every additional recipient.
- **`client/agent.py`'s `_decide_move`** (lines 143, 162) calls `build_prompt(...)` twice with identical arguments on an invalid-move retry, rebuilding the full persona/memory/board text from scratch instead of appending the error suffix to the already-built prompt (the way the adjacent unparseable-JSON branch already does).
