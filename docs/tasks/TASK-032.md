## TASK-032: Wire PatchValidationError into executor error flow

Type: IMPLEMENTATION
Depends_on: [TASK-012, TASK-027]

Objective:
Catch `PatchValidationError` raised by `coder.py` and `fixer.py` inside the executor, emit the appropriate failed trace events, transition to BLOCKED, and return a deterministic `ExecutionResult` rather than propagating an unhandled exception.

Context (spec refs):
- PRD §7.5: "Write scope enforced per task. Diff size threshold enforced."
- constraints.yml: `diff_validation.hard_fail_on_exceed: true`

Current state:
`coder.py` and `fixer.py` raise `PatchValidationError` (defined in `coder.py`) when scope or diff-threshold limits are exceeded. The executor calls `run_coder_session` and `run_fixer_session` with no `try/except` around them. A `PatchValidationError` propagates as an unhandled exception with no trace event emitted and no clean BLOCKED transition.

Inputs:
- `aiw/orchestrator/executor.py` (existing)
- `aiw/orchestrator/coder.py` (existing — `PatchValidationError` defined here, raised by both coder and fixer on scope/diff violations)

Outputs (artifacts/files created or changed):
- `aiw/orchestrator/executor.py`
- `tests/test_executor_fixer.py`

File scope allowlist:
- aiw/orchestrator/executor.py
- tests/test_executor_fixer.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
Wrap the `run_coder(...)` and `run_fixer(...)` calls in `execute_task` with a `try/except PatchValidationError` block. On catch:
1. Emit `scope_validation` with `{"task_id": task_id, "phase": phase, "status": "failed", "detail": str(exc)}`.
2. Emit `diff_threshold_check` with `{"task_id": task_id, "phase": phase, "status": "failed", "detail": str(exc)}`.
3. Transition to BLOCKED via `_transition(..., "on:exhaustion")`.
4. Emit `blocked` with `{"task_id": task_id, "reason": "patch_validation_failed"}`.
5. Emit `run_complete` with `{"task_id": task_id, "status": "BLOCKED", "iterations_used": <n>}`.
6. Return `ExecutionResult(status="BLOCKED", iterations_used=<n>, run_id=run_id)`. Do not re-raise.

Constraints enforced:
- `write_scope_validation.enabled`: true
- `diff_validation.hard_fail_on_exceed`: true

Non-goals:
- No changes to `PatchValidationError`, `scope_validator.py`, or `coder.py`/`fixer.py`.
- No distinction between scope vs. diff violations at the trace level beyond the exception message detail.

Acceptance criteria (measurable):
- A `PatchValidationError` from `coder_runner` results in `ExecutionResult(status="BLOCKED")`, not an unhandled exception.
- `scope_validation` event with `status: "failed"` is emitted before the BLOCKED transition.
- State transitions to BLOCKED.
- `test_executor_fixer.py` includes a test using a mock `coder_runner` that raises `PatchValidationError`, verifying all of the above.
- Same coverage for `fixer_runner` raising `PatchValidationError`.

Tests / checks required:
- `pytest tests/test_executor_fixer.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- `scope_validation` and `diff_threshold_check` events emitted with `status: "failed"` on `PatchValidationError`.
- `blocked` and `run_complete` events emitted with correct payloads.

Rollback plan:
- `git checkout` to pre-task baseline.
