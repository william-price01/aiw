## TASK-023: Integration tests — happy path

Type: TESTING
Depends_on: [TASK-028]

Objective:
Write end-to-end integration tests for the happy path: init through execution PASS, verifying the full workflow state machine progression and trace event emission.

Context (spec refs):
- PRD §9 (acceptance criteria)
- All workflow transitions from PRD §5.2

Inputs:
- All implemented components via CLI entry point

Outputs (artifacts/files created or changed):
- `tests/integration/test_happy_path.py`
- `tests/integration/__init__.py`
- `tests/conftest.py` (shared fixtures)

File scope allowlist:
- tests/integration/test_happy_path.py
- tests/integration/__init__.py
- tests/conftest.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- Tests use subprocess or direct function calls.
- Temporary git repos for isolation (conftest fixtures).

Constraints enforced:
- All constraints exercised via happy path.

Non-goals:
- No error path tests (done in TASK-029).
- No unit test rewrites.

Acceptance criteria (measurable):
- Test: init → prd → approve-prd → sdd → approve-sdd → adrs → approve-adrs → constraints → approve-constraints → decompose → go → PASS → PLANNED.
- Trace events emitted correctly for happy path.
- Artifacts created at each stage.
- State transitions verified at each step.

Tests / checks required:
- `pytest tests/integration/test_happy_path.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Tests verify trace events emitted correctly.

Rollback plan:
- `git checkout` to pre-task baseline.
