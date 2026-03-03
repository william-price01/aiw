## TASK-009: Task lint preflight gate

Type: IMPLEMENTATION
Depends_on: [TASK-003, TASK-026]

Objective:
Implement a preflight lint check that validates a TASK-###.md file has all required fields and scope consistency before execution is permitted.

Context (spec refs):
- SDD §8 (task lint preflight gate)
- constraints.yml: `agents.task_scoped_coding_agent`

Inputs:
- `docs/tasks/TASK-###.md` file
- `docs/constraints.yml` (for scope consistency)

Outputs (artifacts/files created or changed):
- `aiw/tasks/lint.py`
- `aiw/tasks/__init__.py` (updated)
- `tests/test_task_lint.py`

File scope allowlist:
- aiw/tasks/lint.py
- aiw/tasks/__init__.py
- tests/test_task_lint.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `lint_task(task_path: Path, constraints: ConstraintsConfig) -> list[str]` — returns list of lint errors.
- Required fields: acceptance criteria, tests, file scope allowlist, non-goals.
- Scope must not include forbidden paths from constraints.yml.

Constraints enforced:
- `agents.task_scoped_coding_agent.task_id_regex`: `^TASK-\d{3}$`
- `write_scope_validation.forbid_paths`

Non-goals:
- No execution (done in TASK-015).
- No CLI integration (done in TASK-021).

Acceptance criteria (measurable):
- Valid task file returns empty error list.
- Missing acceptance criteria detected.
- Missing tests detected.
- Missing file scope detected.
- Missing non-goals detected.
- File scope including `.aiw/**` detected as violation.
- Emits `task_lint_failed` event data on failure.

Tests / checks required:
- `pytest tests/test_task_lint.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Returns structured data for `task_lint_failed` trace event.

Rollback plan:
- `git checkout` to pre-task baseline.
