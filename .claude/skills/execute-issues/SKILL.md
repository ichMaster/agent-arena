---
name: execute-issues
description: Execute GitHub issues for a version sequentially - implement, validate, commit, push, and generate a report.
---

# Skill: Execute GitHub Issues

Execute GitHub issues for a version sequentially: implement, validate, commit, push, and generate a report.

## Usage

```
/execute-issues <label> [--issue ARENA-xxx] [--dry-run]
```

The `<label>` is the GitHub version label (e.g., `v01.01::phase`).

- `/execute-issues v01.01::phase` -- execute all issues labeled with that phase
- `/execute-issues v01.01::phase --issue ARENA-003` -- execute a single issue from that phase
- `/execute-issues v01.01::phase --dry-run` -- show execution plan without making changes

## Instructions

### Step 0: Verify prerequisites

1. Confirm working tree is clean (`git status`)
2. Confirm `gh` is authenticated
3. Parse the label to determine version (e.g., `v01.01`)
4. Fetch issues from GitHub:
   ```bash
   gh issue list --label "{label}" --state open --limit 100
   ```
5. Read the version issues file for detailed descriptions: `spec/implementation/v{XX.YY}-issues.md`
6. If a GitHub report exists (`spec/implementation/v{XX.YY}-github-report.md`), read the ARENA-to-GitHub# mapping
7. Read the core specs (`spec/roadmap.md`, `spec/architecture.md`) to ensure architecture constraints are honored.

### Step 1: Build execution queue

From the GitHub issue list, build an ordered queue based on dependencies:
- Parse ARENA-xxx IDs from issue titles (format: `ARENA-xxx: {title}`)
- Determine dependency order from the version issues file dependency tree
- Issues with no unmet dependencies go first
- Skip issues already closed on GitHub

Show the user the execution plan and ask for confirmation.

### Step 2: Execute each issue (loop)

For each issue in the queue:

#### 2a. Assign and announce

Print: `--- Starting ARENA-xxx: {title} ---`

#### 2b. Read issue details

Read the full issue description from the version issues file.

#### 2c. Implement

Execute the tasks described in the issue. Follow the project structure defined in `spec/architecture.md`:

- **server/**: The Game Server (FastAPI). Ensure strict separation of the WebSocket Connection Manager, the SQLAlchemy Database models, and the abstract Game Interfaces.
- **agent/**: The Agent CLI. Ensure the `LLMClient` abstraction seam is strictly respected and network logic is completely segregated from persona parsing.
- **web/**: The Web UI. Ensure it uses native JS WebSockets and Glassmorphism styling per `spec/web_ui_specification.md`.
- **designer/**: The builder scripts and YAML profile configurations.
- **Contract changes:** Any change to a stable seam (like the JSON WebSocket payload schemas or GameInterface) must update `spec/architecture.md` and its contract tests in the same commit.

#### 2d. Validate

Run validation checks (Python):

1. **Tests:** `pytest` for the changed packages.
2. **Acceptance criteria:** Go through each criterion from the issue and verify.
3. **Mocks:** Never make paid API calls during testing. Always mock the `LLMClient` to return deterministic JSON tool calls.

Record pass/fail for each check. **Tests are part of the work.**

#### 2e. Commit

```bash
git add {specific files created/modified}
git commit -m "$(cat <<'EOF'
ARENA-xxx: {title}

{1-2 sentence summary of what was implemented}

Closes #{github-issue-number}
EOF
)"
```

#### 2f. Push

```bash
git push
```

#### 2g. Close issue with summary

```bash
gh issue close {issue-number} --comment "$(cat <<'EOF'
## Implementation Summary

**Commit:** {commit-hash}
**Files changed:** {count}

### What was done
{bullet list of key changes}

### Validation
{pass/fail status for each check}

### Acceptance criteria
{checklist with pass/fail}
EOF
)"
```

#### 2h. Log progress

Append to the in-memory execution log.

### Step 3: Handle failures

If implementation or validation fails for an issue:
1. Do NOT commit broken code
2. Revert changes: `git checkout -- .`
3. Add a comment to the GitHub issue explaining what failed
4. Ask the user: continue to next issue (if no dependency), or stop?

### Step 4: Generate execution report

After all issues are processed (or on stop), generate `spec/implementation/v{XX.YY}-execution-report.md`.

Commit and push the report.

## Important Rules

- **One issue at a time.** Never work on multiple issues simultaneously.
- **Dependency order.** Never start an issue whose dependencies are not closed.
- **Clean commits.** Each issue = one commit. No mixing work across issues.
- **No broken code.** Only commit code that passes validation (tests).
- **Tests ship with the feature.** Mock the LLM provider; never call paid APIs during CI/validation.
- **Ask on ambiguity.** If an issue description is unclear, ask the user rather than guessing.
