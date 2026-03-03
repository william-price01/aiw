## TASK-018: Stale EXECUTING recovery

Type: IMPLEMENTATION
Depends_on: [TASK-002, TASK-027]

Objective:
Implement startup detection of stale EXECUTING state and deterministic transition to BLOCKED.

Context (spec refs):
- PRD §12 (de-risk: stale EXECUTING → BLOCKED)
- SDD §5.3 (crash / stale EXECUTING determinism)
- ADR-011: Deterministic crash handling
- constraints.yml: `execution.stale_execution_policy`

Inputs:
- `.aiw/workflow_state.json` on startup

Outputs (artifacts/files created or changed):
- `aiw/workflow/recovery.py`
- `tests/test_recovery.py`

File scope allowlist:
- aiw/workflow/recovery.py
- tests/test_recovery.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `check_stale_execution(state_path: Path) -> bool` — returns True if stale detected.
- `recover_stale_execution(state_path: Path) -> None` — transitions to BLOCKED, emits event.
- Called at startup of any `aiw` command.

Constraints enforced:
- `execution.stale_execution_policy.enabled`
- `execution.stale_execution_policy.on_detect_EXECUTING_at_startup.transition_to`: BLOCKED
- `execution.stale_execution_policy.on_detect_EXECUTING_at_startup.emit_event`: stale_execution_detected

Non-goals:
- No automatic resume.
- No partial execution continuation.

Acceptance criteria (measurable):
- If state=EXECUTING at startup: transitions to BLOCKED.
- Emits `stale_execution_detected` event.
- No automatic retry.
- User must manually resolve to return to PLANNED.

Tests / checks required:
- `pytest tests/test_recovery.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Emits `stale_execution_detected` trace event.

Rollback plan:
- `git checkout` to pre-task baseline.
