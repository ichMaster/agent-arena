---
name: ship-phase
description: Full delivery pipeline, releasing per VERSION. For each version - build every phase (generate-issues -> upload-issues -> execute-issues -> review-and-fix-issues -> HARDEN the remaining HIGH/MEDIUM findings), then release the version ONCE, then generate the next version (reconciled against the real implementation), and finally a report to chat. Gated; stops on failure; surfaces real decisions.
---

# Skill: Ship Phase — the full delivery pipeline (release per version)

Drive the **entire SDLC loop, releasing once per version**. For each version in scope:

- **Build every phase** in the version, in dependency order, each through:
  1. **`generate-issues`** — decompose the phase into an issues file (reconciled against the *real*
     implementation of prior phases/versions — see that skill's Step 0.5).
  2. **`upload-issues`** — push those issues to GitHub (labels, deps, report).
  3. **`execute-issues`** — implement → validate → commit → **push** → close each issue (statuses
     change, one commit per issue), then write the execution report.
  4. **`review-and-fix-issues`** — code-review the phase, write a criticality-ranked recommendations
     doc, implement the fix-now items with regression tests, record the results in that same doc.
  5. **HARDEN** — fix **all remaining HIGH/MEDIUM findings** from the run's code-review reports (the
     ones deferred as "not for immediate fix"), each with a regression test, updating those reports.
     LOW stays deferred to its home.
- **Then `release-version` ONCE for the version** — after every phase is built + hardened.
- **Then the next version** — its `generate-issues` reconciles against what was really built + fixed.

**Finally, generate a report to chat** summarizing everything shipped.

This skill is a **thin orchestrator** — it sequences the sub-skills, adds the HIGH/MEDIUM hardening
sweep, releases per version, and gates between steps; each sub-skill keeps its full discipline.

> **This pipeline releases.** Invoking `/ship-phase` is the explicit opt-in to the automated,
> per-version release (a real tag + push). `release-version`'s own rules still hold — it never
> downgrades and confirms the changelog. To build without releasing, use the individual skills.

## Usage

```
/ship-phase <version|phase|range>
```

- `/ship-phase v02` — build all of v02's phases (v02.01 → v02.02 → …), then release **v02 once**.
- `/ship-phase v02-v03` — do v02 (build phases + release), then v03, then a final report.
- `/ship-phase v02.02` — build the single phase **v02.02** (no version release unless it's the version's
  last phase; a lone-phase target only releases if that phase completes its version).

## Instructions

### Step 0: Scope, baseline, and the version → phase plan

1. Normalize the argument to a **version** (`vXX`), a **phase** (`vXX.YY`), or a **range** (`vXX-vYY`).
2. Read [spec/roadmap.md](../../../spec/roadmap.md). Build the plan as **versions, each with its ordered
   phase list** (`### vXX.YY` under `## vXX`, in file order). A bare phase resolves to its version so
   the "release when the version's phases are all done" rule still applies.
3. Confirm we are on the working dev branch and the tree is clean; establish a **green baseline**
   (`pytest` + strict `mypy`). Never start on a red suite — fix a clear flake first or surface it.
4. **Skip already-shipped work.** A version whose release tag (`opus-vXX.<last>.00`) exists is done. A
   phase already executed/reviewed but not released is resumed from its remaining steps (each sub-skill
   is idempotent: `generate` asks overwrite, `upload` dedupes, `execute` skips closed issues).
5. **Confirm the plan once**, then run — do not re-confirm before each sub-step; pause only for the
   genuine blockers in the rules below.

### Step 1: For each version — build every phase (gated), then release once

**Outer loop: for each version in scope, in order.**
**Inner loop: for each phase in the version, in dependency order,** run the five build steps strictly
in sequence — advance only when the previous finished cleanly, and invoke each sub-skill via the
**Skill tool**:

1. **`generate-issues vXX.YY`** → `spec/implementation/vXX.YY-issues.md` (reconciled — Step 0.5 of that
   skill: read the real code + prior `*-execution-report.md` / `*code-review*.md` so the phase builds on
   what was actually implemented and fixed, not stale docs).
2. **`upload-issues @spec/implementation/vXX.YY-issues.md`** → the GitHub issues + `vXX.YY-github-report.md`.
3. **`execute-issues vXX.YY::phase`** → implement/validate/commit/push/close each issue, then
   `vXX.YY-execution-report.md`. (Statuses change; one issue = one commit.)
4. **`review-and-fix-issues vXX.YY`** → the review recommendations doc + fix-now fixes (with tests, LLM
   mocked), recorded in that same doc.
5. **HARDEN — fix every remaining HIGH/MEDIUM finding** (see Step 1b).

**No release inside the inner loop.** When the version's **last** phase is built + hardened, run the
release **once** (Step 1c). Then continue the outer loop to the next version — whose `generate-issues`
reconciles against everything the prior version really shipped.

Gate the hand-offs: upload after generate; execute after the issues exist; review after execute closed
the issues with a green report; **harden after the review's fix-now items are committed**; the **version
release only after every phase is hardened and the suite is green**.

### Step 1b: HARDEN — sweep the code-review reports for remaining HIGH/MEDIUM

Once a phase is built and reviewed, close out the serious findings that `review-and-fix-issues`
**deferred** (real, but not recommended for *immediate* fix). This is `/ship-phase`'s stronger policy:
**no HIGH or MEDIUM finding leaves the pipeline unfixed.**

1. **Collect** every code-review report generated during this run (`spec/implementation/*code-review*.md`).
2. **Select** each finding with severity **🔴 HIGH or 🟠 MEDIUM** whose **Status is not FIXED** —
   **regardless of its `DEFER → <home>` recommendation**. Ignore 🟡 LOW (stays deferred). HIGH before MEDIUM.
3. For each: implement the fix + a **regression test that would have caught it** (LLM mocked); **validate**
   (`pytest` green + strict `mypy`); **commit** one focused change referencing the finding. A **seam
   change** carries its `spec/architecture.md` update + contract test in the same commit.
4. **Update the report in place:** flip that finding's **Status** to `✅ FIXED — <commit>`, extend "Fixes
   applied", and add an **"Architecture impact"** note if the fix changed a documented contract/behavior
   (so the next version's `generate-issues` reconciliation sees it).
5. Re-run the full suite at the end of the sweep to confirm it's green and deterministic.

**Escape hatch:** if a HIGH/MEDIUM fix genuinely can't land safely now (needs a design decision, or
would balloon and risk the release), **do not force a broken fix** — leave it deferred with a reason in
the report and **surface it to the user**. Prefer fixing; hold only when a clean landing isn't possible.

### Step 1c: Release the version (once)

After the version's phases are all built + hardened and the suite is green, invoke
**`release-version`** once for the version — version number = the version's **final phase**
(e.g. `v02.03.00` for v02), changelog spanning the whole version, namespaced tag `opus-vXX.<last>.00`
(the shared repo holds sibling tags). This single release includes all the phase work **plus** the
review fix-now fixes **plus** the HIGH/MEDIUM hardening. Then continue to the next version.

### Step 2: Final report to chat

After all versions in scope are shipped (or the run stops), **report to chat** (not a file):
- **Per version:** the phases built (ARENA-OPUS id range → GitHub #s), the execution commit range +
  test/typing status, the review's finding counts (**fixed-now / hardened HIGH-MEDIUM / LOW deferred**,
  with homes), any **Architecture impact** deltas recorded, and the **release tag**.
- **Overall:** versions shipped, work skipped (already released), any HIGH/MEDIUM **held** via the escape
  hatch (with why), and any phase/version that stopped early (with what remains).
- Point at what's next (the following version, or LOW/held items to carry into their phase).

## Important Rules

- **Release per version, not per phase.** Build (and harden) all of a version's phases first, then run
  `release-version` **once** for the version. Do not release individual phases.
- **Reconcile before the next version.** The next version's `generate-issues` grounds itself in the
  **real implementation** of the prior version (its code + execution/review reports + "Architecture
  impact" notes), not the possibly-stale `architecture.md`. Contract changes made by fixes must be in
  `architecture.md` (with their contract test) so the reconciliation is accurate.
- **Sequential and gated.** Each step's output is the next step's input (issues file → GitHub issues →
  committed code → review/fixes → hardened HIGH/MEDIUM → version release). Never start a step whose
  predecessor didn't finish cleanly, and never interleave two phases' pipelines.
- **No HIGH/MEDIUM left behind.** Step 1b fixes every HIGH and MEDIUM finding before the version release,
  overriding their `DEFER` recommendation; only LOW stays deferred. The lone exception is the escape
  hatch — a HIGH/MEDIUM that can't land safely is held with a reason and surfaced.
- **Stop on failure — do not paper over it.** If any sub-skill fails, or a harden fix hits a red
  `pytest`/`mypy`, **halt the pipeline**, report what completed and what remains, and let the user
  decide. Never release a version whose suite isn't green.
- **Every fix ships a regression test**, the LLM is always mocked (no paid calls), and the suite stays
  green and deterministic.
- **Surface real decisions.** Pause for shared-repo **ID/tag collisions** (use the `opus-` prefix), an
  **overwrite/append** prompt, a **held HIGH/MEDIUM** finding, or any execution/validation failure.
- **Delegate, never duplicate.** This skill sequences the sub-skills and adds the HIGH/MEDIUM sweep +
  per-version release; it adds no other logic. Each sub-skill keeps its discipline — one issue = one
  commit, seam changes carry `spec/architecture.md` + contract test, IDs stay in this branch's
  `ARENA-OPUS-###` namespace, releases use namespaced tags, every line generated fresh.
- **Ask on a bad target.** If the argument doesn't resolve to a real roadmap version/phase, ask.
