---
name: execute-all-phases
description: Sequentially execute all local issue files from spec/implementation, commit, validate, and cut version releases without GitHub interaction.
---

# Skill: Execute All Phases

This skill automates the sequential implementation, validation, and release of all roadmap phases defined in `spec/implementation/*-issues.md` files, without interacting with the GitHub API.

## Usage

```
/execute-all-phases
```

## Instructions

### Step 1: Scan and Order the Implementation Phases
1. Scan the `spec/implementation/` directory for files matching `v*-issues.md`.
2. Order them chronologically (e.g., `v01.01`, `v01.02`, `v01.03`, `v02.01`, etc.).
3. Present the list of phases to be executed to the user.

### Step 2: Sequential Phase Execution Loop
For each phase (e.g., `vXX.YY`):

#### 2.1 Parse Phase Issues
Read the `spec/implementation/vXX.YY-issues.md` file to identify the list of issues, descriptions, tasks, and acceptance criteria.

#### 2.2 Execute Issues Sequentially
For each issue (e.g., `ARENA-xxx`) within the current phase:
1. Implement the tasks described under `What needs to be done`.
2. Run validation checks (e.g., `pytest` or Python scripts).
3. If validation succeeds, stage and commit the changes:
   ```bash
   git add <modified_files>
   git commit -m "ARENA-xxx: <title>
   
   <Short summary of changes>"
   ```
4. If validation fails, revert changes (`git checkout -- .`) and ask the user how to proceed.

#### 2.3 Cut Phase Version Release
After all issues in the current phase are successfully implemented and committed:
1. Determine the release version (e.g., `01.01.00`, `01.02.00`, etc.) corresponding to the phase.
2. Update the `VERSION` file.
3. Update the FastAPI `app` version string in `server/main.py` if it exists.
4. Append release notes to `RELEASE.txt`.
5. Commit the release changes:
   ```bash
   git add VERSION RELEASE.txt server/main.py
   git commit -m "Release vXX.YY.00"
   ```
6. Tag the release commit:
   ```bash
   git tag -f -a vXX.YY.00 -m "Release vXX.YY.00"
   ```
7. Push the commits and tags to origin:
   ```bash
   git push origin Gemini-3.5Flash-dev
   git push origin --tags --force
   ```
8. Generate the execution report `spec/implementation/vXX.YY-execution-report.md` summarizing what was done and the validation results.
9. Commit and push the execution report.

### Step 3: Complete Execution
Once all phases are processed, print a final summary of all versions implemented and released.
