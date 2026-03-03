## TASK-021: CLI entry point — router and arg parsing

Type: IMPLEMENTATION
Depends_on: [TASK-005, TASK-025, TASK-007, TASK-026, TASK-027, TASK-017, TASK-019]

Objective:
Implement the single `aiw` CLI entry point with argument parsing and command dispatch table for all 14 commands. No state validation logic — just routing.

Context (spec refs):
- PRD §5.2 (command allowance by state)
- constraints.yml: `workflow.allowed_commands_by_state`

Inputs:
- All command implementations from prior tasks

Outputs (artifacts/files created or changed):
- `aiw/cli/main.py`
- `aiw/cli/__init__.py` (updated)
- `tests/test_cli_router.py`

File scope allowlist:
- aiw/cli/main.py
- aiw/cli/__init__.py
- tests/test_cli_router.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- Entry point: `aiw <command> [args]`
- Commands: init, prd, approve-prd, sdd, approve-sdd, adrs, approve-adrs, constraints, approve-constraints, decompose, go, undo, reset, request-change.
- Dispatch table routes to command handlers.
- Help text for all commands.
- Exit codes: 0 success, 1 error.
- Unknown commands fail with usage message.

Constraints enforced:
- None directly (state validation deferred to TASK-028).

Non-goals:
- No state validation before dispatch (done in TASK-028).
- No stale execution check (done in TASK-028).
- No TUI (done in TASK-024).

Acceptance criteria (measurable):
- All 14 commands routable via dispatch table.
- Unknown command exits code 1 with usage.
- Help text available (`aiw --help`, `aiw <cmd> --help`).
- Each command dispatches to correct handler.

Tests / checks required:
- `pytest tests/test_cli_router.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Command dispatch logged.

Rollback plan:
- `git checkout` to pre-task baseline.
