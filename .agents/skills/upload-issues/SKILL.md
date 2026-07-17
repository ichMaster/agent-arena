---
name: upload-issues
description: Upload issues from a version issues file to GitHub one by one with proper labels and dependencies.
---

# Skill: Upload Version Issues to GitHub

Upload issues from a version issues file to GitHub one by one, with proper labels (prefixed by version) and dependencies.

## Usage

```
/upload-issues <version-issues-file>
```

Example: `/upload-issues @spec/implementation/v01.01-issues.md`

## Instructions

### Step 1: Read the version issues file

Read the provided file (e.g., `spec/implementation/v{XX.YY}-issues.md`).

Determine from the file:
- **Version number** (e.g., `v01.01`)
- **Label prefix**: `v{XX.YY}::`

Parse the **Issues Summary Table** to extract for each issue:
- `ID` (e.g., ARENA-001)
- `Title`
- `Size` (S, M, L)
- `Area` (the component: `server`, `agent`, `web`, `designer`, `tests`)
- `Dependencies` (list of ARENA-xxx IDs)

Then parse each **detailed issue section** (heading with ARENA-xxx) to extract: `Description`, `What needs to be done`, `Dependencies`, `Expected result`, `Acceptance criteria`.

### Step 2: Confirm with user

Show the user a summary of what will be created: number of issues, label prefix, the full list of labels, and ask for confirmation before proceeding.

### Step 3: Create labels (if they don't exist)

All labels MUST be prefixed with `v{XX.YY}::`. Label format: `v{XX.YY}::{category}:{value}`.

```bash
# Version label
gh label create "v01.01::phase" --color "0E8A16" 2>/dev/null || true

# Size labels
gh label create "v01.01::size:S" --color "28A745" --description "Small (1-2 days)" 2>/dev/null || true
gh label create "v01.01::size:M" --color "FFC107" --description "Medium (3-5 days)" 2>/dev/null || true
gh label create "v01.01::size:L" --color "DC3545" --description "Large (5-8 days)" 2>/dev/null || true

# Area labels
gh label create "v01.01::area:server" --color "6F42C1" 2>/dev/null || true
gh label create "v01.01::area:agent" --color "1D76DB" 2>/dev/null || true
gh label create "v01.01::area:web" --color "E34F26" 2>/dev/null || true
gh label create "v01.01::area:designer" --color "FFC107" 2>/dev/null || true
gh label create "v01.01::area:tests" --color "28A745" 2>/dev/null || true
```

### Step 4: Create issues ONE BY ONE

**IMPORTANT:** Issues must be created one at a time, sequentially. After creating each issue, show the user the result (issue number, URL) and proceed to the next immediately.

For each issue (in order from the summary table):

1. Build the issue body in markdown:

```markdown
## Description
{description}

## What needs to be done
{full content}

## Dependencies
{dependency list, with references to already-created issue numbers}

## Expected result
{expected result}

## Acceptance criteria
{checklist}

---
**ID:** {ARENA-xxx}
**Size:** {S/M/L}
**Version:** v{XX.YY}
**Area:** {server/agent/web/designer/tests}
```

2. Create the issue with a single `gh issue create` command:

```bash
gh issue create \
  --title "ARENA-xxx: {title}" \
  --label "v{XX.YY}::phase,v{XX.YY}::size:{S/M/L},v{XX.YY}::area:{area}" \
  --body "$(cat <<'BODY'
{issue body}
BODY
)"
```

3. Record the mapping: ARENA-xxx -> GitHub issue #number
4. Report to user: `Created ARENA-xxx -> #{number}: {title}`
5. If the issue depends on already-created issues, add a comment:
   ```bash
   gh issue comment {issue-number} --body "Blocked by #{dep-issue-number} (ARENA-xxx)"
   ```
6. Move to the next issue.

### Step 5: Generate report

After all issues are created, generate `spec/implementation/v{XX.YY}-github-report.md`:

```markdown
# Version v{XX.YY} -- GitHub Issues Report

**Uploaded:** {date}
**Repository:** {github repo URL}
**Total issues:** {count}

## Issue Mapping

| ARENA ID | GitHub # | Title | Labels | URL |
|----------|----------|-------|--------|-----|
| ARENA-001 | #5 | ... | v01.01::phase, v01.01::area:server | {url} |
```

### Step 6: Report to user

Show the user: total issues created, link to the GitHub issues page, path to the generated report file.

## Error Handling

- If `gh` is not authenticated, tell the user to run `gh auth login`
- If an issue already exists with the same title, skip it and note in the report
- On any failure, report what was created so far and what remains
