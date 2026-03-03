## TASK-012: Write-scope and diff validation

Type: IMPLEMENTATION
Depends_on: [TASK-003, TASK-004]

Objective:
Implement validation that checks a proposed patch against the task's file scope allowlist, forbidden paths, and diff size thresholds.

Context (spec refs):
- PRD §7.5 (guardrails)
- SDD §9 step 2 (validate patch), §11 (constraint enforcement)
- constraints.yml: `write_scope_validation`, `diff_validation`, `boundaries.internal_tool_state`

Inputs:
- Proposed patch (as file list + diff stats)
- Task file scope allowlist
- constraints.yml scope rules

Outputs (artifacts/files created or changed):
- `aiw/tasks/scope_validator.py`
- `tests/test_scope_validator.py`

File scope allowlist:
- aiw/tasks/scope_validator.py
- tests/test_scope_validator.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `validate_scope(changed_files: list[str], task_allowlist: list[str], constraints: ConstraintsConfig) -> list[str]` — returns violations.
- `validate_diff_size(files_changed: int, lines_changed: int, constraints: ConstraintsConfig) -> list[str]` — returns violations.
- Hard-fail on exceed when `diff_validation.hard_fail_on_exceed` is true.

Constraints enforced:
- `write_scope_validation.enabled`
- `write_scope_validation.allowed_edit_paths`
- `write_scope_validation.forbid_paths` (`.aiw/**`)
- `diff_validation.enabled`
- `diff_validation.max_files_changed`: 30
- `diff_validation.max_lines_changed`: 1500
- `diff_validation.hard_fail_on_exceed`

Non-goals:
- No patch application (done in TASK-013/015).
- No locked artifact checks (done in TASK-004).

Acceptance criteria (measurable):
- Files in task allowlist pass.
- Files outside allowlist flagged.
- `.aiw/**` writes rejected.
- >30 files changed rejected.
- >1500 lines changed rejected.
- Returns structured violation list for trace events.

Tests / checks required:
- `pytest tests/test_scope_validator.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Returns data for `scope_validation` and `diff_threshold_check` trace events.

Rollback plan:
- `git checkout` to pre-task baseline.
