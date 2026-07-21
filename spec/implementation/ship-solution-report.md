# Ship-Solution Execution Report — 2026-07-21

**Branch:** `Anthropic-Opus4.8-Opus4.8-dev` · **Executed by:** Claude Opus 4.8, via `/ship-solution`
**Mode:** commit-only, **no push**, no GitHub (standing constraints for this run) · every line generated
fresh — nothing read, checked out, or copied from any sibling branch.

## Total

- **Wall-clock:** 1h 19m 0s (all 15 versions, all 5 phases, end to end)
- **Phases:** 5 · **Versions:** 15 · **Issues executed:** 37 · **Commits:** 96
- **Releases:** `opus-opus-v01.01.00` → `opus-opus-v05.03.00` (all 15, one per version — local annotated tags, never pushed)
- **Findings:** fix-now fixed **5** · hardened HIGH/MEDIUM via a phase-boundary sweep **0** (see Notes) · LOW deferred **6** · held **0**
- **Reconcile:** issues corrected **6** · moot **0** · untouched **31** (of 37)
- **Suite:** 0 → **189** tests passing · `mypy --strict` clean (19 source files) throughout · zero paid model calls anywhere (LLM always mocked; enforced by an autouse guard from v05.02)

## By phase

| Phase | Versions | Duration | Issues | Commits | Reconciled (corr/moot) | Fix-now | Hardened | Release tags | HARDEN patch |
|-------|----------|----------|--------|---------|------------------------|---------|----------|--------------|--------------|
| v01 — Game Core & Server Foundation | 4 | 27m 30s | 15 | 34 | 0/0 | 1 | 0 | v01.01.00 → v01.04.00 | none (no-op sweep) |
| v02 — Agent Client (Haiku) | 3 | 17m 55s | 9 | 20 | 0/0 | 2 | 0 | v02.01.00 → v02.03.00 | none (no-op sweep) |
| v03 — Web UI (Player & Observer) | 3 | 16m 25s | 7 | 19 | 0/1 | 1 | 0 | v03.01.00 → v03.03.00 | none (no-op sweep) |
| v04 — Agent-vs-Agent Orchestration | 2 | 5m 16s | 2 | 8 | 1/0 | 0 | 0 | v04.01.00 → v04.02.00 | none (no-op sweep) |
| v05 — Hardening & Polish | 3 | 10m 11s | 4 | 14 | 4/0 | 1 | 0 | v05.01.00 → v05.03.00 | none (no-op sweep) |

Commit counts are `git rev-list --count` between consecutive release tags. They sum to **96** — the
branch's true total from the first `/ship-solution` commit (the CLAUDE.md commit, exclusive) through
the final `v05.03.00` release.

## By version

| Version | Duration | Issues | Commits | Tests (before→after) | Reconcile (corr/moot/untouched) | Review (fix-now/deferred) | Release tag |
|---------|----------|--------|---------|----------------------|----------------------------------|----------------------------|-------------|
| v01.01 | 6m 26s | 3 | 10 | 0 → 22 (scaffolding: skeleton, `GameInterface`, TicTacToe) | 0/0/3 | 0/0 | opus-opus-v01.01.00 |
| v01.02 | 7m 26s | 4 | 8 | 22 → 47 | 0/0/4 | 0/1 | opus-opus-v01.02.00 |
| v01.03 | 5m 36s | 4 | 8 | 47 → 64 | 0/0/4 | 0/0 | opus-opus-v01.03.00 |
| v01.04 | 8m 02s | 4 | 8 | 64 → 89 | 0/0/4 | 0/2 | opus-opus-v01.04.00 |
| v02.01 | 4m 59s | 3 | 6 | 89 → 105 | 0/0/3 | 0/0 | opus-opus-v02.01.00 |
| v02.02 | 6m 16s | 3 | 8 | 105 → 126 | 0/0/3 | 2/0 | opus-opus-v02.02.00 |
| v02.03 | 6m 40s | 3 | 6 | 126 → 138 | 0/0/3 | 0/1 | opus-opus-v02.03.00 |
| v03.01 | 5m 37s | 3 | 6 | 138 → 150 | 0/0/3 | 0/0 | opus-opus-v03.01.00 |
| v03.02 | 4m 29s | 2 | 5 | 150 → 158 | 0/0/2 | 0/1 | opus-opus-v03.02.00 |
| v03.03 | 6m 19s | 2 | 8 | 158 → 167 | 0/2/0 | 1/0 | opus-opus-v03.03.00 |
| v04.01 | 2m 30s | 1 | 4 | 167 → 170 | 1/0/0 | 0/0 | opus-opus-v04.01.00 |
| v04.02 | 2m 46s | 1 | 4 | 170 → 176 | 0/0/1 | 0/0 | opus-opus-v04.02.00 |
| v05.01 | 4m 20s | 1 | 6 | 176 → 181 | 2/0/0 | 1/0 | opus-opus-v05.01.00 |
| v05.02 | 2m 43s | 2 | 5 | 181 → 183 | 0/0/2 | 0/0 | opus-opus-v05.02.00 |
| v05.03 | 3m 08s | 1 | 4 | 183 → 189 | 3/0/0 | 0/0 | opus-opus-v05.03.00 |

(The "corr" reconcile counts are per-issue drift corrections within a version; several versions carried
a namespace-rename that isn't counted as drift. v01.01's commit count includes the run's one-time setup
— the CLAUDE.md/`.gitignore`/skeleton commits.)

## Timings

- **Fastest version:** v04.01 (2m 30s) — a single small persona-data issue, no findings.
- **Slowest version:** v01.04 (8m 02s) — the v01 gate: the full WS move-authority flow + the §10
  shielded-cleanup path, plus two deferred LOWs.
- **Average per version:** 5m 09s (15 versions).
- **Per-phase totals:** v01 27m 30s · v02 17m 55s · v03 16m 25s · v04 5m 16s · v05 10m 11s.

## Notes

- **Every HIGH/MEDIUM finding was fixed at its own version's review step — no phase ever needed a
  HARDEN patch.** All 5 end-of-phase HARDEN sweeps were genuine no-ops (verified by scanning each
  phase's `*-code-review.md` for unresolved 🔴/🟠 rows): v01 (0), v02 (v02.02's MEDIUM fixed in-flow),
  v03 (v03.03's MEDIUM fixed in-flow), v04 (0), v05 (v05.01's MEDIUM fixed in-flow). No
  `opus-opus-vXX.YY.01` patch tag exists anywhere on this branch.
- **The 5 fix-now fixes** (all MEDIUM/LOW, none HIGH): v02.02 — a prompt-injection guard (opponent chat
  framed as never-instructions) **and** a chat-length cap; v03.03 — the server now refuses a seatless
  connection's `chat`; v05.01 — the WS loop no longer crashes on malformed JSON **and** (in review) on
  a binary frame. Each shipped with a regression test.
- **6 LOWs remain deferred**, correctly (HARDEN only ever touches HIGH/MEDIUM): the move-log
  double-reconstruction perf item (v01.02), malformed-JSON-then-fixed-in-v05.01 + observer-chat-then-
  fixed-in-v03.03 (both were *deferred at v01.04, then actually closed* in their homed versions), the
  generic opponent-card label (v03.02, needs a protocol field — out of MVP scope), the bare-traceback
  CLI ergonomics (v02.03), and the v01.02 perf item re-homed via v05.01's review note. The still-open
  ones (opponent-label, move-log perf, CLI traceback) are all genuinely out of the MVP DoD.
- **Reconciliation caught real, not cosmetic, drift** — the pre-generated issues were drafted for a
  *different* build:
  - **v03.03:** a false "the server already refuses observer chat (v01.04 #3)" citation — it didn't;
    the real gap became this version's MEDIUM fix.
  - **v04.01 / v05.02:** the aggressive persona was drafted as "Blaze"; the real, test-pinned shipped
    name is `Ironclaw`.
  - **v05.01:** the file claimed malformed-JSON-kept-alive was already shipped ("v02.03.01 HARDEN #4")
    — verified empirically that it **wasn't** (a raw non-JSON frame crashed the connection), and closed
    it as this version's own production fix; also corrected a `v02.03.01` patch tag and a
    `test_ws_resilience.py` that don't exist on this branch.
  - **v05.03:** the file assumed a "3-line stub" README and an existing `.env.example` — the `main`
    cleanup had removed **both**, so this version *created* them; and the install extra is `[dev]`, not
    `[test]`.
  - **v02.02 / v02.03:** removed stale "code-review finding #7" citations (no such finding exists on
    this branch) while keeping the sound underlying `.env`-at-the-CLI scoping.
- **One HIGH-class risk was pre-empted, not hit:** the `uvicorn`-not-declared gap (the README's first
  command failing on a clean install) never occurred here because `uvicorn` was declared as a runtime
  dependency back in v01.03; v05.03's doc-smoke test pins it so it can't drift out.
- **Nothing stopped early; nothing was held.** All 15 versions, all 5 phases, and this report completed
  in one continuous run. The gitignored scratch timing file
  (`spec/implementation/.ship-solution-progress.md`) is deleted after this report rolls its content in.
