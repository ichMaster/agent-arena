---
name: ship-phase
description: Run the full generate -> upload -> execute pipeline for one roadmap phase (vXX.YY), or every phase in a version (vXX) in dependency order. Chains /generate-issues, /upload-issues, and /execute-issues; never releases.
---

# Skill: Ship Phase (generate -> upload -> execute)

Drive the whole SDLC loop for a roadmap **phase** in one command: decompose it into an issues
file (`/generate-issues`), push those issues to GitHub (`/upload-issues`), then implement, validate,
commit, push, and close them (`/execute-issues`). Given a **version** (`vXX`), do this for **every
phase in that version, in roadmap order**, completing each phase's full pipeline before the next.

This skill is a **thin orchestrator** — it only sequences the three underlying skills and gates
between them. It does **not** re-implement their logic, and it **never** bumps the version
(`/release-version` stays a separate, explicit step).

## Usage

```
/ship-phase <phase|version>
```

- `/ship-phase v02.01` — run generate -> upload -> execute for phase **v02.01**.
- `/ship-phase v02` — run the full pipeline for **every phase under v02** (v02.01, v02.02, …), in order.
- `/ship-phase 2.1` — same as `v02.01` (normalize/zero-pad first).

## Instructions

### Step 0: Parse the target and build the phase list

1. Normalize the argument:
   - `vXX.YY` (or `XX.YY`, `X.Y`) -> a single **phase** `vXX.YY`.
   - `vXX` (or `XX`, `X`) -> a **version**; expand to its phases (next step).
2. If a **version**: read [spec/roadmap.md](../../../spec/roadmap.md), find the `## vXX — …` version
   heading, and collect **every `### vXX.YY — …` phase under it, in file order** -> the ordered phase
   list. If a **phase**: the list is just that one phase.
3. **Skip already-shipped phases.** For each phase, if it looks complete — a
   `spec/implementation/v{XX.YY}-execution-report.md` exists **and** `gh issue list --label
   "v{XX.YY}::phase" --state open` returns nothing — mark it **skipped (already shipped)** and drop it
   from the run. (Ask the user only if the state is ambiguous, e.g. a report exists but issues are
   still open.)
4. **Confirm the plan once**, then proceed: list the phases to run and the three steps each. Because
   the user explicitly invoked the full pipeline, do **not** stop to re-confirm before each sub-step —
   run straight through, pausing only for the genuine blockers in the rules below.

### Step 1: For each phase in the list, in order — run the three steps, gated

Do these **strictly in sequence**; only advance when the previous step finished cleanly. Invoke each
underlying skill through the **Skill tool** (it loads that skill's instructions; follow them fully).

1. **Generate** — invoke `generate-issues` with the phase (e.g. `generate-issues v{XX.YY}`).
   Produces `spec/implementation/v{XX.YY}-issues.md`. If the file already exists, `generate-issues`
   asks overwrite/append — surface that choice to the user.
2. **Upload** — invoke `upload-issues` with `@spec/implementation/v{XX.YY}-issues.md`. Creates the
   `v{XX.YY}::` labels + the issues on GitHub and writes `v{XX.YY}-github-report.md`.
3. **Execute** — invoke `execute-issues` with `v{XX.YY}::phase`. Implements -> validates
   (`pytest` + `mypy`, LLM mocked) -> commits -> pushes -> closes each issue in dependency order,
   then writes `v{XX.YY}-execution-report.md`.

Advance to Upload only after Generate wrote the file; to Execute only after Upload created the
issues; to the **next phase** only after Execute closed all of this phase's issues with a green
report. In version mode this ordering matters — a later phase usually depends on the earlier one
being **executed** (its code committed), not merely planned.

### Step 2: Report

After the list is exhausted (or the run stops), summarize:
- Phases **shipped** (ARENA-OPUS id range + GitHub #s per phase), phases **skipped** (already done),
  and any phase that **stopped early** (with why and what remains).
- The commit range and the final `pytest` + `mypy` status.
- Point at the natural next step: `/release-version vXX.YY.00` per completed phase (never run
  automatically), or `/ship-phase` for the next version.

## Important Rules

- **Sequential and gated.** Each step's output is the next step's input: generate -> the issues file
  -> upload -> the GitHub issues -> execute. Never start a step whose predecessor didn't finish
  cleanly, and never run two phases' pipelines interleaved.
- **Stop on failure — do not paper over it.** If `generate-issues`, `upload-issues`, or
  `execute-issues` fails, or `execute-issues` reports a validation failure (a red `pytest`/`mypy`, a
  broken build), **halt the whole pipeline**, report exactly what completed and what remains, and let
  the user decide. Do not continue to the next step or next phase on a failure.
- **Surface real decisions; don't answer for the user.** When an underlying skill needs a genuine
  choice — the shared-repo **ID-namespace collision** in `upload-issues`, an **ambiguous phase scope**
  in `generate-issues`, an **overwrite/append** prompt, or an execution failure — pause and ask. Only
  the routine "here's the plan" confirmations in the sub-skills are safe to run straight through.
- **Version = phases in dependency order.** Expand a version to its phases from the roadmap and run
  them in order, each pipeline fully complete before the next begins.
- **Delegate, never duplicate.** This skill sequences the three sub-skills and gates between them; it
  adds no new logic. Every sub-skill keeps its own discipline — one issue = one commit, the LLM always
  mocked (no paid calls), seam changes carry their `spec/architecture.md` update + contract test, IDs
  stay in this branch's `ARENA-OPUS-###` namespace, and every line is generated fresh (never copied
  from a sibling branch).
- **Never release.** This skill stops after `execute-issues`. It does **not** run `/release-version`
  or bump any version metadata — the user cuts releases explicitly, per phase.
- **Ask on a bad target.** If the argument doesn't resolve to a real roadmap phase or version, ask
  rather than guessing.
