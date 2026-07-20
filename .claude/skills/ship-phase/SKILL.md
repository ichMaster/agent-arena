---
name: ship-phase
description: Full delivery pipeline over the roadmap. For each phase (vXX) run its versions (vXX.YY) in order - RECONCILE with the real implementation, generate-issues, upload-issues, execute-issues, review-and-fix-issues, HARDEN remaining HIGH/MEDIUM findings, then release-version vXX.YY.00 (release per VERSION). When a phase completes, report it to chat. Gated; stops on failure; surfaces real decisions.
---

# Skill: Ship Phase — the full delivery pipeline

Drive the entire SDLC loop over the roadmap: **phases contain versions; each version is released;
the next version is generated only after the previous one is implemented and fixed** — reconciled
against the real (post-fix) implementation.

> **Terminology (per [game_specification.md](../../../spec/game_specification.md) §6):** a **phase**
> is a top-level roadmap block `vXX` (Phase 1 → `v01` … Phase 5 → `v05`); a **version** is a `vXX.YY`
> sub-version inside it, released as `vXX.YY.00`. ⚠️ The roadmap's header and the four sub-skills use
> these words the other way around (they call `vXX.YY` a "phase" — hence the GitHub label
> `vXX.YY::phase` and the invocation `generate-issues <vXX.YY>`). The sub-skill invocations below are
> exactly as they've always been; only this skill's flow description uses the spec's wording.

**The loop:**

```
for each PHASE vXX (in roadmap order):
    for each VERSION vXX.YY in the phase (in order):
        0. RECONCILE   — ground this version in the real implementation + all prior fixes
        1. generate-issues vXX.YY
        2. upload-issues @spec/implementation/vXX.YY-issues.md
        3. execute-issues vXX.YY::phase        (implement → validate → commit → push → close)
        4. review-and-fix-issues vXX.YY        (review → ranked doc → fix-now fixes → same doc)
        5. HARDEN                              (fix ALL remaining HIGH/MEDIUM findings)
        6. release-version vXX.YY.00           ← RELEASE PER VERSION (tag opus-vXX.YY.00)
    → phase complete: REPORT the phase to chat
→ next phase; after the whole scope: overall summary to chat
```

This skill is a **thin orchestrator** — it sequences the sub-skills, adds the reconcile gate and the
HIGH/MEDIUM hardening sweep, and releases per version; each sub-skill keeps its full discipline.

> **This pipeline releases.** Invoking `/ship-phase` is the explicit opt-in to the automated
> per-version releases (real tags + pushes). `release-version`'s own rules still hold — it never
> downgrades and confirms the changelog. To build without releasing, use the individual skills.

## Usage

```
/ship-phase <phase|version|range>
```

- `/ship-phase v02` — ship **phase v02**: every version in it (v02.01 → v02.02 → v02.03), each through
  all six steps incl. its own release, then the phase report to chat.
- `/ship-phase v02.02` — ship the single **version v02.02** through all six steps (incl. its release).
- `/ship-phase v02-v03` — ship phase v02, then phase v03, then an overall summary.

## Instructions

### Step 0: Scope, baseline, and the phase → version plan

1. Normalize the argument to a **phase** (`vXX`), a **version** (`vXX.YY`), or a **range** (`vXX-vYY`).
2. Read [spec/roadmap.md](../../../spec/roadmap.md). Build the plan: for each phase in scope, its
   ordered version list (`### vXX.YY` headings under `## vXX`, in file order).
3. Confirm we are on the working dev branch and the tree is clean; establish a **green baseline**
   (`pytest` + strict `mypy`). Never start on a red suite — fix a clear flake first or surface it.
4. **Skip already-shipped versions** (release tag `opus-vXX.YY.00` exists). A version partially done
   (issues/report exist but no tag) resumes from its remaining steps — each sub-skill is idempotent
   (`generate` asks overwrite, `upload` dedupes, `execute` skips closed issues, `release` refuses a
   downgrade).
5. **Confirm the plan once**, then run — do not re-confirm before each sub-step; pause only for the
   genuine blockers in the rules below.

### Step 1: For each phase → for each version — the six steps, gated

Run the versions **strictly in sequence** — version N+1 starts only after version N is **released**
(implemented, reviewed, fixed, hardened, tagged). That sequencing is the point: the next version's
issues are generated against the previous version's *real, fixed* implementation. Invoke each
sub-skill via the **Skill tool** (it loads that skill's instructions; follow them fully).

**0. RECONCILE** — the first act of every version's cycle, carried out **inside `generate-issues`
   (its Step 0.5)**: before decomposing `vXX.YY`, read (a) the **real current code** of the components
   it touches, (b) prior `spec/implementation/*-execution-report.md`, and (c) prior
   `spec/implementation/*code-review*.md` — especially their **"Fixes applied"** and **"Architecture
   impact"** notes from the review/harden steps. Where fixes drifted the code from `architecture.md`,
   the implementation is ground truth; doc corrections ride along in the seam-touching issue. This is
   where "changes in architecture after fixes" enter the next version's issues.
1. **`generate-issues vXX.YY`** → `spec/implementation/vXX.YY-issues.md` (reconciled, per step 0).
2. **`upload-issues @spec/implementation/vXX.YY-issues.md`** → the GitHub issues + labels + deps +
   `vXX.YY-github-report.md`.
3. **`execute-issues vXX.YY::phase`** → implement → validate → commit → **push** → close each issue in
   dependency order (statuses change; one issue = one commit), then `vXX.YY-execution-report.md`.
4. **`review-and-fix-issues vXX.YY`** → code review, the criticality-ranked recommendations doc, the
   fix-now fixes (with regression tests, LLM mocked), results recorded **in that same doc** (incl.
   "Architecture impact" notes for behavior/contract-changing fixes).
5. **HARDEN** — fix **every remaining HIGH/MEDIUM finding** from the run's code-review reports
   (see Step 1b). LOW stays deferred to its home.
6. **`release-version vXX.YY.00`** → bump `VERSION`/`RELEASE.txt`/the app version, tag (namespaced
   `opus-vXX.YY.00` — the shared repo holds sibling tags), and push. **Release per version.**

Gate the hand-offs: upload only after generate wrote the file; execute only after the issues exist;
review only after execute closed the issues with a green report; harden only after the review's
fix-now items are committed; **release only after the harden sweep is committed and the suite is
green**; the **next version only after this one is released**.

### Step 1b: HARDEN — sweep the code-review reports for remaining HIGH/MEDIUM

Before a version is released, close out the serious findings that `review-and-fix-issues` **deferred**
(real, but not recommended for *immediate* fix). This is `/ship-phase`'s stronger policy: **no HIGH or
MEDIUM finding leaves the pipeline unfixed.**

1. **Collect** every code-review report generated during this run (`spec/implementation/*code-review*.md`).
2. **Select** each finding with severity **🔴 HIGH or 🟠 MEDIUM** whose **Status is not FIXED** —
   **regardless of its `DEFER → <home>` recommendation**. Ignore 🟡 LOW (stays deferred). HIGH before
   MEDIUM. (Findings hardened in an earlier version's sweep are already `✅ FIXED` and skip naturally.)
3. For each: implement the fix + a **regression test that would have caught it** (LLM mocked, no paid
   call); **validate** (`pytest` green + strict `mypy`); **commit** one focused change referencing the
   finding (`fix(<area>): … (code review #N)`). A **seam change** carries its `spec/architecture.md`
   update + contract test in the same commit.
4. **Update the report in place:** flip the finding's **Status** to `✅ FIXED — <commit>`, extend
   "Fixes applied", and add an **"Architecture impact"** note if the fix changed documented
   behavior/contracts — the next version's RECONCILE step reads exactly these notes.
5. Re-run the full suite at the end of the sweep to confirm green and deterministic.

**Escape hatch:** if a HIGH/MEDIUM fix genuinely can't land safely now (needs a design decision, or
would balloon and risk the release), don't force a broken fix — leave it deferred with the reason in
the report and **surface it to the user before releasing**. Prefer fixing; hold only when a clean
landing isn't possible.

> Note: HIGH/MEDIUM findings homed to a *later* roadmap version (e.g. v05.01 resilience) get fixed
> here instead — mark that later scope as already addressed so it isn't re-done when its version comes.

### Step 2: Phase complete → report the phase to chat

When a phase's last version is released, **report the phase to chat** (not a file):
- **Per version:** ARENA-OPUS id range → GitHub #s, execution commit range + test/typing status, review
  finding counts (**fixed-now / hardened HIGH-MEDIUM / LOW deferred**, with homes), any **Architecture
  impact** deltas recorded, and the release tag.
- **Phase rollup:** what the phase delivered against its roadmap goal, and anything held via the
  escape hatch.

Then continue to the next phase. After the whole scope, add a short **overall summary** (phases
shipped, versions skipped as already-released, anything stopped early and what remains, what's next).

## Important Rules

- **Release per VERSION (`vXX.YY.00`)** — after that version is built, reviewed, fixed, and hardened.
  Never batch several versions into one release, and never release mid-version.
- **Next version only after the previous is released.** The strict sequencing is what makes the
  RECONCILE step meaningful: version N+1's issues are generated against version N's real, fixed code.
- **Reconciliation is step 0 of every version** (via `generate-issues` Step 0.5): real code + execution
  reports + review docs' "Fixes applied"/"Architecture impact" are the input to the next version's
  issues; `architecture.md` corrections ride along in seam-touching issues.
- **No HIGH/MEDIUM left behind.** Step 1b fixes every HIGH and MEDIUM finding before the version's
  release, overriding their `DEFER` recommendation; only LOW stays deferred. Sole exception: the escape
  hatch — held with a reason and surfaced.
- **Sequential and gated.** Each step's output is the next step's input. Never start a step whose
  predecessor didn't finish cleanly; never interleave two versions' pipelines.
- **Stop on failure — do not paper over it.** If any sub-skill fails, or any fix hits a red
  `pytest`/`mypy`, halt, report what completed and what remains, and let the user decide. Never release
  a version whose suite isn't green.
- **Every fix ships a regression test**, the LLM is always mocked (no paid calls), and the suite stays
  green and deterministic.
- **Surface real decisions.** Pause for shared-repo **ID/tag collisions** (use the `opus-` prefix per
  the established pattern), an **overwrite/append** prompt, a **held HIGH/MEDIUM**, or any
  execution/validation failure. Routine plan confirmations run straight through.
- **Delegate, never duplicate.** This skill sequences the sub-skills and adds RECONCILE + HARDEN +
  per-version releasing; no other logic. Each sub-skill keeps its discipline — one issue = one commit,
  seam changes carry `spec/architecture.md` + contract test, IDs stay in this branch's
  `ARENA-OPUS-###` namespace, releases use namespaced tags, every line generated fresh (never copied
  from a sibling branch).
- **Ask on a bad target.** If the argument doesn't resolve to a real roadmap phase/version, ask.
