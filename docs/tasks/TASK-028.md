## TASK-028: CLI entry point — state validation and stale check

Type: IMPLEMENTATION
Depends_on: [TASK-021, TASK-018]

Objective:
Add state validation middleware to the CLI router: before dispatching any command, validate it is allowed in the current workflow state, and run the stale EXECUTING check on startup.

Context (spec refs):
- PRD §5.2 (command allowance by state — invalid commands fail deterministically)
- SDD §5.3 (stale EXECUTING detection)
- constraints.yml: `workflow.allowed_commands_by_state`, `workflow.illegal_actions_must_fail_hard`

Inputs:
- CLI router (TASK-021)
- Stale recovery (TASK-018)
- State machine (TASK-002)

Outputs (artifacts/files created or changed):
- `aiw/cli/main.py` (extended)
- `tests/test_cli_state.py`

File scope allowlist:
- aiw/cli/main.py
- tests/test_cli_state.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- Before dispatch: check `workflow.allowed_commands_by_state[current_state]`.
- If command not allowed: exit code 1, error message with current state and allowed commands.
- On startup: call `check_stale_execution` from TASK-018.
- If stale detected: transition to BLOCKED, inform user.

Constraints enforced:
- `workflow.allowed_commands_by_state`
- `workflow.illegal_actions_must_fail_hard`
- `execution.stale_execution_policy`

Non-goals:
- No new commands.
- No router changes.

Acceptance criteria (measurable):
- `aiw go TASK-001` in INIT state exits code 1 with error.
- `aiw decompose` in PRD_DRAFT state exits code 1 with error.
- Error message shows current state and allowed commands.
- Stale EXECUTING detected → BLOCKED on any command invocation.
- All state/command combinations tested.

Tests / checks required:
- `pytest tests/test_cli_state.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- State validation failures logged.

Rollback plan:
- `git checkout` to pre-task baseline.
