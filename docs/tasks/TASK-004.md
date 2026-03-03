## TASK-004: Artifact locking engine

Type: IMPLEMENTATION
Depends_on: [TASK-002]

Objective:
Implement artifact locking that prevents modification of locked files based on workflow state, using git diff --name-only for detection.

Context (spec refs):
- PRD §5.3 (locking rules)
- SDD §6 (locking rules — explicit)
- constraints.yml: `boundaries.locked_artifacts`, `locking_rules`

Inputs:
- Current workflow state from state machine (TASK-002)
- constraints.yml locked_artifacts config

Outputs (artifacts/files created or changed):
- `aiw/workflow/locking.py`
- `tests/test_locking.py`

File scope allowlist:
- aiw/workflow/locking.py
- tests/test_locking.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `get_locked_paths(state: str) -> set[str]` — returns paths locked in given state.
- `check_lock_violations(state: str, changed_files: list[str]) -> list[str]` — returns violating paths.
- Uses `git diff --name-only` to detect changed files.
- On violation: raises `LockViolationError`.

Constraints enforced:
- `boundaries.locked_artifacts.lock_after_state`
- `boundaries.locked_artifacts.immutable_during_execution`
- `locking_rules.forbid_silent_edits_to_locked_artifacts`
- `locking_rules.hard_fail_on_locked_artifact_modification_during_EXECUTING`
- `locking_rules.locked_artifacts_checked_via_git_diff_name_only`

Non-goals:
- No revert logic (done in TASK-011).
- No trace emission (done in TASK-010).

Acceptance criteria (measurable):
- After PRD_APPROVED: docs/prd.md in locked set.
- After SDD_APPROVED: docs/sdd.md in locked set.
- After ADRS_APPROVED: docs/adrs/** in locked set.
- After CONSTRAINTS_APPROVED: docs/constraints.yml in locked set.
- During EXECUTING: DAG.md, DAG.yml, TASK-???.md in locked set.
- `check_lock_violations` returns violating paths correctly.
- LockViolationError raised on violation.

Tests / checks required:
- `pytest tests/test_locking.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Returns data for `lock_violation_hard_fail` event (emitted by caller).

Rollback plan:
- `git checkout` to pre-task baseline.
