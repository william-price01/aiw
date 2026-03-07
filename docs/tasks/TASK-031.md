## TASK-031: Wire lock enforcement into executor patch-validation step

Type: IMPLEMENTATION
Depends_on: [TASK-004, TASK-027]

Objective:
Call `check_lock_violations` inside the executor's patch-validation step before applying any patch, emit `lock_violation_hard_fail` on violation, and raise to abort the run.

Context (spec refs):
- PRD §5.3, SDD §6: "Any attempt to modify locked artifacts causes: immediate hard-fail, emit `lock_violation_hard_fail`, abort run."
- SDD §9 step 2: "Validate patch: write scope, locked artifact diffs, diff size thresholds." All three must happen before apply.

Current state:
`executor.py`'s `_emit_patch_validation_events` unconditionally emits `scope_validation` and `diff_threshold_check` with `status: "passed"` without ever calling `check_lock_violations`. The lock check is fully implemented in `locking.py` (`check_lock_violations`, `LockViolationError`) but never invoked from the executor.

Inputs:
- `aiw/orchestrator/executor.py` (existing)
- `aiw/workflow/locking.py` (existing — `check_lock_violations`, `LockViolationError`)

Outputs (artifacts/files created or changed):
- `aiw/orchestrator/executor.py`
- `tests/test_executor_happy.py`

File scope allowlist:
- aiw/orchestrator/executor.py
- tests/test_executor_happy.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
Extend `_emit_patch_validation_events` (or extract a new `_validate_patch` helper) to call `check_lock_violations("EXECUTING", list(patch_result.changed_files))` before emitting scope/diff events. On `LockViolationError`:
1. Emit `lock_violation_hard_fail` with `{"task_id": task_id, "phase": phase, "violations": list(e.violations)}`.
2. Re-raise as `ExecutionError` to abort the run.

The `status` field in `scope_validation` and `diff_threshold_check` events must reflect actual outcome. Do not emit them as `"passed"` when a lock violation has already been detected.

Constraints enforced:
- `locking_rules.hard_fail_on_locked_artifact_modification_during_EXECUTING`: true
- `locking_rules.forbid_silent_edits_to_locked_artifacts`: true
- `locking_rules.locked_artifacts_checked_via_git_diff_name_only`: true

Non-goals:
- No revert-to-checkpoint logic on lock violation (abort is sufficient for correctness here).
- No changes to `locking.py`.

Acceptance criteria (measurable):
- A patch touching `docs/tasks/DAG.md` during EXECUTING raises `ExecutionError`.
- `lock_violation_hard_fail` event is emitted with the violating path before the error.
- `scope_validation` and `diff_threshold_check` are NOT emitted as `"passed"` when a lock violation precedes them.
- `test_executor_happy.py` includes at least one test verifying this behavior via a mock `coder_runner` that returns a patch with a locked file in `changed_files`.

Tests / checks required:
- `pytest tests/test_executor_happy.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- `lock_violation_hard_fail` event emitted with task_id, phase, and violations list.

Rollback plan:
- `git checkout` to pre-task baseline.
