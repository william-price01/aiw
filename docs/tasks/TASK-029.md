## TASK-029: Integration tests — error and BLOCKED paths

Type: TESTING
Depends_on: [TASK-023]

Objective:
Write end-to-end integration tests for error paths: invalid state transitions, locked artifact violations, diff threshold enforcement, execution exhaustion → BLOCKED, and stale EXECUTING recovery.

Context (spec refs):
- PRD §9 (acceptance criteria)
- PRD §5.3 (locking), §7.5 (guardrails), §12 (de-risk: stale recovery)

Inputs:
- All implemented components via CLI entry point
- Shared fixtures from TASK-023

Outputs (artifacts/files created or changed):
- `tests/integration/test_error_paths.py`
- `tests/conftest.py` (extended if needed)

File scope allowlist:
- tests/integration/test_error_paths.py
- tests/conftest.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- Tests use subprocess or direct function calls.
- Temporary git repos for isolation.

Constraints enforced:
- All error-path constraints exercised.

Non-goals:
- No happy path tests (done in TASK-023).
- No new features.

Acceptance criteria (measurable):
- Test: execution exhaustion → BLOCKED with blocker report generated.
- Test: every invalid state transition rejected (at least one per state).
- Test: locked artifact modification rejected during EXECUTING.
- Test: diff threshold exceeded rejected.
- Test: stale EXECUTING → BLOCKED on startup.
- Test: constraints gate refusal with placeholder values.
- All tests pass with `pytest tests/integration/test_error_paths.py -q`.

Tests / checks required:
- `pytest tests/integration/test_error_paths.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Tests verify error trace events emitted correctly.

Rollback plan:
- `git checkout` to pre-task baseline.
