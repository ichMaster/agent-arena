---
name: ship-phase
description: Full delivery pipeline, by version. Per phase - generate-issues -> upload-issues -> execute-issues -> review-and-fix-issues -> HARDEN (fix every remaining HIGH/MEDIUM finding from the run's code-review reports) -> release-version. Then the next version, then a report to chat. Gated; stops on failure; surfaces real decisions.
---

# Skill: Ship Phase — the full delivery pipeline

Drive the **entire SDLC loop by version**. For each phase in the target version, in dependency order,
run the underlying skills end to end and harden before releasing:

1. **`generate-issues`** — decompose the phase into an issues file.
2. **`upload-issues`** — push those issues to GitHub (labels, deps, report).
3. **`execute-issues`** — implement → validate → commit → **push** → close each issue (statuses change,
   one commit per issue), then write the execution report.
4. **`review-and-fix-issues`** — code-review the phase, write a criticality-ranked recommendations doc,
   implement the fix-now items with regression tests, and record the results in that same doc.
5. **HARDEN** — sweep **every code-review report produced during this run** and fix **all remaining
   HIGH and MEDIUM findings** (the ones deferred as "not recommended for immediate fix"), each with a
   regression test, updating those reports — so the release ships fully hardened. LOW findings stay
   deferred to their homes.
6. **`release-version`** — bump the version, update files, tag, and **push** the phase release.

Then move to the next phase; when the version's phases are exhausted, move to the **next version**.
**Finally, generate a report to chat** summarizing everything shipped.

This skill is a **thin orchestrator** — it sequences the sub-skills, adds the HIGH/MEDIUM hardening
sweep, and gates between steps; each sub-skill keeps its full discipline.

> **This pipeline releases.** Invoking `/ship-phase` is the explicit opt-in to the automated, per-phase
> releases in step 6 (a real tag + push). `release-version`'s own rules still hold — it never
> downgrades and confirms the changelog. To build without releasing, use the individual skills.

## Usage

```
/ship-phase <version|phase|range>
```

- `/ship-phase v02` — ship **every phase in v02**, in order (v02.01 → v02.02 → …), each through all six
  steps, then a final report.
- `/ship-phase v02.02` — ship the single phase **v02.02** through all six steps.
- `/ship-phase v02-v03` — ship v02 then v03 (phase by phase), then report.

## Instructions

### Step 0: Scope, baseline, and the phase list

1. Normalize the argument to a **version** (`vXX`), a **phase** (`vXX.YY`), or a **range** (`vXX-vYY`).
2. Expand to an **ordered phase list**: read [spec/roadmap.md](../../../spec/roadmap.md); for each version
   in scope, collect its `### vXX.YY` phases in file order. A bare phase → a one-item list.
3. Confirm we are on the working dev branch and the tree is clean; establish a **green baseline**
   (`pytest` + strict `mypy`). Never start on a red suite — fix a clear flake first or surface it.
4. **Skip already-shipped phases** (release tag `opus-vXX.YY.00` exists). For a partially-done phase,
   run only the remaining steps (each sub-skill is idempotent: `generate` asks overwrite, `upload`
   dedupes, `execute` skips closed issues, `release` refuses a downgrade).
5. **Confirm the plan once**, then run — do not re-confirm before each sub-step; pause only for the
   genuine blockers in the rules below.

### Step 1: For each phase, in order — run the six steps, gated

Do these **strictly in sequence**; advance only when the previous step finished cleanly. Invoke each
underlying skill through the **Skill tool** (it loads that skill's instructions; follow them fully).

1. **`generate-issues vXX.YY`** → `spec/implementation/vXX.YY-issues.md`.
2. **`upload-issues @spec/implementation/vXX.YY-issues.md`** → the GitHub issues + `vXX.YY-github-report.md`.
3. **`execute-issues vXX.YY::phase`** → implement/validate/commit/push/close each issue in dependency
   order, then `vXX.YY-execution-report.md`. (Statuses change; one issue = one commit.)
4. **`review-and-fix-issues vXX.YY`** → the review recommendations doc, the fix-now fixes (with
   regression tests, LLM mocked), and the results recorded **in that same doc**.
5. **HARDEN — fix every remaining HIGH/MEDIUM finding** (see Step 1b below).
6. **`release-version vXX.YY.00`** → bump `VERSION`/`RELEASE.txt`/the app version, tag (namespaced,
   e.g. `opus-vXX.YY.00`, since the shared repo holds sibling tags), and push.

Gate the hand-offs: upload only after generate wrote the file; execute only after the issues exist;
review only after execute closed the issues with a green report; **harden only after the review's
fix-now items are committed**; **release only after the harden sweep's HIGH/MEDIUM fixes are committed
and the suite is green**. Advance to the **next phase** only after this phase is released.

### Step 1b: HARDEN — sweep the code-review reports for remaining HIGH/MEDIUM

Once the phase is built and reviewed (steps 3–4 done), before releasing, close out the serious
findings that `review-and-fix-issues` **deferred** (they were real but not recommended for *immediate*
fix). This is `/ship-phase`'s stronger policy on top of that skill's default: **no HIGH or MEDIUM
finding leaves the pipeline unfixed.**

1. **Collect** every code-review report generated during this run —
   `spec/implementation/*code-review*.md` (the docs `review-and-fix-issues` writes).
2. **Select** each finding whose **severity is 🔴 HIGH or 🟠 MEDIUM** and whose **Status is not FIXED**
   (i.e. `⏳ deferred`/pending) — **regardless of its `DEFER → <home>` recommendation**. Ignore 🟡 LOW
   findings (they stay deferred to their homes). Process **HIGH before MEDIUM**.
3. For each selected finding: implement the fix + a **regression test that would have caught it** (LLM
   always mocked, no paid call); **validate** (`pytest` green + strict `mypy`); **commit** one focused
   change referencing the finding (`fix(<area>): … (code review #N)`, with the `Co-Authored-By`
   trailer). A **seam change** carries its `spec/architecture.md` update + contract test in the same
   commit.
4. **Update the report in place:** flip that finding's **Status** to `✅ FIXED — <commit>` and extend the
   report's "Fixes applied" section. Commit the doc update.
5. Re-run the full suite once at the end of the sweep to confirm it's green and deterministic.

**Escape hatch:** if a HIGH/MEDIUM fix genuinely can't be landed safely now — it needs a design
decision, or would balloon into a large change that risks the release — **do not force a broken or
half-baked fix.** Leave it deferred, note in the report *why* it's held and its target, and **surface
it to the user** before releasing (this is a genuine decision, per the rules). Prefer fixing; hold
only when landing it cleanly isn't possible.

> Sweeping "all reports" is cheap across phases: findings fixed in an earlier phase's sweep are already
> `✅ FIXED` and skipped, so each phase's sweep effectively clears the fresh HIGH/MEDIUM from its own
> review. Deferred HIGH/MEDIUM that were homed to a *later* roadmap phase (e.g. v05.01) get fixed here
> instead — mark that phase's later scope as already addressed so it isn't re-done.

### Step 2: Next phase / next version

When a phase is released, move to the next phase in the version; when the version's phases are done,
move to the next version in scope. Keep the branch state clean between phases.

### Step 3: Final report to chat

After the phase list is exhausted (or the run stops), **report to chat** (not a file):
- **Per phase:** the ARENA-OPUS id range → GitHub #s, the execution commit range + test/typing status,
  the review's finding counts (**fixed-now / hardened HIGH-MEDIUM / LOW deferred**, with homes), and the
  release tag.
- **Overall:** phases shipped, phases skipped (already released), any HIGH/MEDIUM held via the escape
  hatch (with why), and any phase that stopped early (with what remains).
- Point at what's next (the following version, or LOW/held items to carry into their phase).

## Important Rules

- **Sequential and gated.** Each step's output is the next step's input (issues file → GitHub issues →
  committed code → review/fixes → hardened HIGH/MEDIUM → release). Never start a step whose predecessor
  didn't finish cleanly, and never interleave two phases' pipelines.
- **No HIGH/MEDIUM left behind.** Step 1b fixes every HIGH and MEDIUM finding from the run's review
  reports before release, overriding their `DEFER` recommendation. Only LOW findings stay deferred to
  their homes. The one exception is the escape hatch above — a HIGH/MEDIUM that can't be landed safely
  now is held with a reason and surfaced to the user.
- **Stop on failure — do not paper over it.** If any sub-skill fails, or a fix in the harden sweep hits
  a red `pytest`/`mypy`, **halt the pipeline**, report what completed and what remains, and let the user
  decide. Do not release a phase whose suite isn't green.
- **Every fix ships a regression test**, the LLM is always mocked (no paid calls), and the suite stays
  green and deterministic — the harden sweep is held to the same bar as `execute`/`review-and-fix`.
- **Surface real decisions; don't answer for the user.** Pause for the shared-repo **ID/tag
  collisions** (use the `opus-` prefix), an **overwrite/append** prompt, a **held HIGH/MEDIUM** finding,
  or any execution/validation failure. Routine "here's the plan" confirmations run straight through.
- **Delegate, never duplicate.** This skill sequences the sub-skills and adds the HIGH/MEDIUM sweep; it
  adds no other logic. Each sub-skill keeps its discipline — one issue = one commit, seam changes carry
  `spec/architecture.md` + contract test, IDs stay in this branch's `ARENA-OPUS-###` namespace, releases
  use namespaced tags, and every line is generated fresh (never copied from a sibling branch).
- **Review and harden before release.** Steps 4 and 5 always precede step 6, so each phase is reviewed,
  its fix-now items fixed, and its remaining HIGH/MEDIUM findings resolved before it is tagged.
- **Ask on a bad target.** If the argument doesn't resolve to a real roadmap version/phase, ask.
