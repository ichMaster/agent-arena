# Post-Code Generation Error Report

This document tracks the issues and bugs encountered after the initial code generation phase. These errors required manual intervention or follow-up debugging sessions to resolve.

## Summary Statistics

| Error Category | Incidents | Total Files Affected | Total Lines Changed |
| :--- | :---: | :---: | :---: |
| **Business Logic Errors** | 7 | 24 | 91 |
| **Agent / Infrastructure Errors** | 2 | 2 | 9 |
| **Total** | **9** | **26** | **100** |

## Detailed Breakdown

### Business Logic Errors
These issues primarily involved game state management, WebSocket payload structures, or backend routing logic:
1. `business logic error` -- 3 files, 6 lines modified
2. `business logic error` -- 2 files, 7 lines modified
3. `business logic error` -- 6 files, 18 lines modified
4. `business logic error` -- 5 files, 5 lines modified
5. `business logic error` -- 2 files, 15 lines modified
6. `business logic error` -- 2 files, 18 lines modified
7. `business logic error` -- 4 files, 22 lines modified

### Agent / Infrastructure Errors
These issues involved the CLI scripts, environment variables, or LLM endpoint integration (e.g., 404 Model Not Found and WebSocket synchronization):
1. `agent error` -- 1 file, 4 lines modified
2. `agent error` -- 1 file, 5 lines modified

---
*Note: All listed errors have been successfully addressed, debugged, and patched in the current branch.*
