## TASK-003: Constraints loader and validator

Type: IMPLEMENTATION
Depends_on: [TASK-001]

Objective:
Implement a loader that parses `docs/constraints.yml` into a typed configuration object and validates that required fields are present and non-placeholder.

Context (spec refs):
- PRD §7.3 (constraints finalization gate)
- SDD §7 (deterministic constraints gate)
- constraints.yml (full schema)

Inputs:
- `docs/constraints.yml` file

Outputs (artifacts/files created or changed):
- `aiw/infra/constraints.py`
- `aiw/infra/__init__.py` (updated)
- `tests/test_constraints.py`

File scope allowlist:
- aiw/infra/constraints.py
- aiw/infra/__init__.py
- tests/test_constraints.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `ConstraintsConfig` dataclass/TypedDict with typed fields for all constraint sections.
- `load_constraints(path: Path) -> ConstraintsConfig`
- `validate_constraints(config: ConstraintsConfig) -> list[str]` returns list of validation errors.
- Rejects placeholder values: `"TBD"`, `""`.

Constraints enforced:
- `execution.constraints_finalization_gate.required_non_placeholder_fields`
- `execution.constraints_finalization_gate.placeholder_values`

Non-goals:
- No gate enforcement (done in TASK-007).
- No layer boundary checking (done in TASK-022).

Acceptance criteria (measurable):
- Loads valid constraints.yml without error.
- Returns typed config with all sections accessible.
- Detects missing `quality.test_command`.
- Detects placeholder "TBD" and empty string values in required fields.
- Returns validation error list (empty if valid).

Tests / checks required:
- `pytest tests/test_constraints.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- None (passive loader).

Rollback plan:
- `git checkout` to pre-task baseline.
