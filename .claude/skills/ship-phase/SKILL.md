---
name: ship-phase
description: Full delivery pipeline, by version. For each phase in a version, in order - generate-issues -> upload-issues -> execute-issues -> review-and-fix-issues -> release-version - then the next version, then a final report to chat. Gated between steps; stops on failure; surfaces real decisions.
---

# Skill: Ship Phase — the full delivery pipeline

Drive the **entire SDLC loop by version**. For each phase in the target version, in dependency order,
run the five underlying skills end to end:

1. **`generate-issues`** — decompose the phase into an issues file.
2. **`upload-issues`** — push those issues to GitHub (labels, deps, report).
3. **`execute-issues`** — implement → validate → commit → **push** → close each issue (statuses change,
   one commit per issue), then write the execution report.
4. **`review-and-fix-issues`** — code-review the phase, write a criticality-ranked recommendations doc,
   implement the fix-now items with regression tests, and record the results in that same doc.
5. **`release-version`** — bump the version, update files, tag, and **push** the phase release.

Then move to the next phase; when the version's phases are exhausted, move to the **next version**.
**Finally, generate a report to chat** summarizing everything shipped.

This skill is a **thin orchestrator** — it sequences the five skills and gates between them; it adds
no logic of its own and each sub-skill keeps its full discipline.

> **This pipeline releases.** Invoking `/ship-phase` is the explicit opt-in to the automated,
> per-phase releases in step 5 (a real tag + push). `release-version`'s own rules still hold — it
> never downgrades and confirms the changelog. If you want to build without releasing, use the
> individual skills (or stop the run before step 5).

## Usage

```
/ship-phase <version|phase|range>
```

- `/ship-phase v02` — ship **every phase in v02**, in order (v02.01 → v02.02 → …), each through all
  five steps, then a final report.
- `/ship-phase v02.02` — ship the single phase **v02.02** through all five steps.
- `/ship-phase v02-v03` — ship v02 then v03 (phase by phase), then report.

## Instructions

### Step 0: Scope, baseline, and the phase list

1. Normalize the argument to a **version** (`vXX`), a **phase** (`vXX.YY`), or a **range** (`vXX-vYY`).
2. Expand to an **ordered phase list**: read [spec/roadmap.md](../../../spec/roadmap.md); for each version
   in scope, collect its `### vXX.YY` phases in file order. A bare phase → a one-item list.
3. Confirm we are on the working dev branch and the tree is clean; establish a **green baseline**
   (`pytest` + strict `mypy`). Never start on a red suite — fix a clear flake first or surface it.
4. **Skip already-shipped phases.** A phase whose **release tag already exists** (e.g. `opus-vXX.YY.00`)
   is done — mark it skipped and drop it. For a partially-done phase (issues/report/review exist but no
   tag), run only the remaining steps (each sub-skill is idempotent: `generate` asks overwrite,
   `upload` dedupes, `execute` skips closed issues, `release` refuses a downgrade).
5. **Confirm the plan once**, then run: list the phases and the five steps each. The user opted into the
   full pipeline by invoking it — do **not** re-confirm before each sub-step; pause only for the
   genuine blockers in the rules below.

### Step 1: For each phase, in order — run the five steps, gated

Do these **strictly in sequence**; advance only when the previous step finished cleanly. Invoke each
underlying skill through the **Skill tool** (it loads that skill's instructions; follow them fully).

1. **`generate-issues vXX.YY`** → `spec/implementation/vXX.YY-issues.md`.
2. **`upload-issues @spec/implementation/vXX.YY-issues.md`** → the GitHub issues + `vXX.YY-github-report.md`.
3. **`execute-issues vXX.YY::phase`** → implement/validate/commit/push/close each issue in dependency
   order, then `vXX.YY-execution-report.md`. (Statuses change; one issue = one commit.)
4. **`review-and-fix-issues vXX.YY`** → the review recommendations doc, the fix-now fixes (with
   regression tests, LLM mocked), and the results recorded **in that same doc**.
5. **`release-version vXX.YY.00`** → bump `VERSION`/`RELEASE.txt`/the app version, tag (namespaced,
   e.g. `opus-vXX.YY.00`, since the shared repo holds sibling tags), and push.

Gate the hand-offs: upload only after generate wrote the file; execute only after the issues exist;
review only after execute closed the issues with a green report; release only after the review's fixes
are committed and the suite is green. Advance to the **next phase** only after this phase is released.
In version mode this ordering matters — a later phase usually depends on the earlier one being
**executed and released** (its code committed), not merely planned.

### Step 2: Next phase / next version

When a phase is released, move to the next phase in the version; when the version's phases are done,
move to the next version in scope. Keep the branch state clean between phases.

### Step 3: Final report to chat

After the phase list is exhausted (or the run stops), **report to chat** (not a file):
- **Per phase:** the ARENA-OPUS id range → GitHub #s, the execution commit range + test/typing status,
  the review's finding counts (fixed vs deferred, with homes), and the release tag.
- **Overall:** phases shipped, phases skipped (already released), and any phase that stopped early
  (with why and what remains).
- Point at what's next (the following version, or deferred review items to carry into their phase).

## Important Rules

- **Sequential and gated.** Each step's output is the next step's input (issues file → GitHub issues →
  committed code → review/fixes → release). Never start a step whose predecessor didn't finish cleanly,
  and never interleave two phases' pipelines.
- **Stop on failure — do not paper over it.** If any sub-skill fails, or `execute-issues`/
  `review-and-fix-issues` hits a red `pytest`/`mypy`, **halt the whole pipeline**, report what
  completed and what remains, and let the user decide. Do not release a phase whose suite isn't green,
  and do not advance to the next phase on a failure.
- **Surface real decisions; don't answer for the user.** Pause for genuine choices — the shared-repo
  **ID-namespace collision** and **tag collision** (use the `opus-` prefix per the established pattern),
  an **ambiguous phase scope**, an **overwrite/append** prompt, a **borderline fix-now-vs-defer** call,
  or any execution/validation failure. Routine "here's the plan" confirmations run straight through.
- **Version = phases in dependency order.** Expand each version from the roadmap; run its phases in
  order, each pipeline fully complete before the next.
- **Delegate, never duplicate.** This skill only sequences the five sub-skills; it adds no logic. Each
  keeps its discipline — one issue = one commit, the LLM always mocked (no paid calls), every fix ships
  a regression test, seam changes carry their `spec/architecture.md` update + contract test, IDs stay
  in this branch's `ARENA-OPUS-###` namespace, releases use namespaced tags, and every line is
  generated fresh (never copied from a sibling branch).
- **Review before release.** Step 4 (review-and-fix) always runs before step 5 (release), so each
  phase is reviewed and its fix-now issues fixed before it is tagged.
- **Ask on a bad target.** If the argument doesn't resolve to a real roadmap version/phase, ask.
