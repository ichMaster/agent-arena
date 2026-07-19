---
name: generate-issues
description: Decompose a roadmap phase into a per-phase GitHub-issues file at spec/implementation/, ready for /upload-issues.
---

# Skill: Generate Version Issues

Decompose one ROADMAP **version/phase** (`vXX.YY.00`) into a fine-grained, dependency-ordered
**issues file**, written to `spec/implementation/`. The output is the input to `/upload-issues` (which pushes it to GitHub) and then `/execute-issues` (which implements it).

## Usage

```
/generate-issues <version>
```

- `/generate-issues v01.01` — decompose ROADMAP version **v01.01.00** → `spec/implementation/v01.01-issues.md`
- `/generate-issues 02.01` — phase **v02.01.00** → `…/v02.01-issues.md`

One file per **sub-version** (`vXX.YY`). IDs (`ARENA-xxx`) are **globally sequential** and continue across phase files.

## Instructions

### Step 0: Read inputs

1. Normalize the version to `vXX.YY` (e.g. `01.01` → `v01.01`).
2. Read [spec/roadmap.md](../../../spec/roadmap.md) §`vXX.YY` — the version's **Goal**, **Tasks**, and **DoD**.
3. Read [spec/architecture.md](../../../spec/architecture.md) for the contracts and components the phase touches, and the other spec files (`game_specification.md`, `web_ui_specification.md`).
4. **Find the next free `ARENA-xxx` id:** scan existing `spec/implementation/v*-issues.md`; continue from the highest id used. If none exist yet, start at `ARENA-001`.
5. If `…/v{XX.YY}-issues.md` already exists, ask whether to overwrite or append.

### Step 1: Decompose the phase

Turn the phase's **Tasks** into a small set of issues (typically **3–7**), each a coherent, independently shippable slice:

- Size each **S** (1–2 d) / **M** (3–5 d) / **L** (5–8 d).
- Order by dependency; the first issue is usually the **gate** (the seam/structure everything else builds on).
- Map each issue to part of the phase Tasks; together they must satisfy the phase **DoD**.
- **Bake tests into every issue:** unit for pure logic, contract for any seam, integration where relevant. Ensure the LLM provider is mocked in tests.
- A seam change carries an ARCHITECTURE update + its contract test in the **same** issue.
- Stay **within the phase** — don't pull later phases' scope in early.

### Step 2: Write the issues file

Write `spec/implementation/v{XX.YY}-issues.md` using **exactly** this format:

````markdown
# v{XX.YY} — GitHub Issues

Issues for phase **v{XX.YY}**, derived from the per-phase Tasks in [roadmap.md](../../roadmap.md).
This file is scoped to a single phase; IDs continue from the previous phase (ARENA-{prev} → **ARENA-{first}…{last}**).

## Issues Summary Table

| # | ID | Title | Size | Area | Dependencies |
|---|----|-------|------|------|--------------|
| 1 | ARENA-{first} | {title} | M | {server/agent/web/designer} | -- |
| 2 | ARENA-{…} | {title} | S | {area} | ARENA-{first} |
| … | … | … | … | … | … |

**Size legend:** S = 1–2 days, M = 3–5 days, L = 5–8 days

---

## Dependency Tree

```
ARENA-{first} ({gate})
  |
  +-- ARENA-{…} (…) --+
  |                   |
  +-- ARENA-{…} (…) --+
                      |
             ARENA-{…} (…)  => {phase DoD}
```

---

## v{XX.YY} Tasks

### ARENA-{id} — {Title}

**Description:**
{1–3 sentences. Note which module(s) it touches.}

**What needs to be done:**
- {bullet}
- {bullet}

**Dependencies:** {ARENA-ids, or None}

**Expected result:**
{one sentence}

**Acceptance criteria:**
- [ ] {functional criterion}
- [ ] **Contract test:** {seam pinned} — *(only if a seam changes)*
- [ ] **Unit test:** {pure logic}
- [ ] {ties to the phase DoD}

---

{repeat the `### ARENA-{id} …` block per issue}

## v{XX.YY} scope notes

**Phase DoD:** {restate the DoD}.
**Contracts pinned this phase:** {the seams + their tests}.
**Companion documents:**
- [roadmap.md](../../roadmap.md)
- [architecture.md](../../architecture.md)
````

### Step 3: Report

Show the user: the file path, the issue count, the `ARENA-xxx` id range, and the critical path. Suggest the next step:

```
/upload-issues @spec/implementation/v{XX.YY}-issues.md
```

(Do **not** create GitHub issues here — that's `/upload-issues`. This skill only writes the local issues file.)

## Important Rules

- **One file per phase** (`vXX.YY`) at `spec/implementation/v{XX.YY}-issues.md`.
- **IDs are globally sequential** (`ARENA-xxx`).
- **Tests in every issue.** Acceptance criteria include unit/integration tests.
- **Seam = ARCHITECTURE + test together.**
- **Don't touch GitHub.** This skill writes only the local file; `/upload-issues` pushes it.
