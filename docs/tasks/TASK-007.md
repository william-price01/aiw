## TASK-007: Constraints finalization gate

Type: IMPLEMENTATION
Depends_on: [TASK-003, TASK-025]

Objective:
Implement the preflight gate that validates constraints.yml before allowing `aiw decompose` or `aiw go`, refusing execution if required fields are missing or placeholder.

Context (spec refs):
- PRD §7.3 (constraints finalization gate)
- SDD §7 (deterministic constraints gate — preflight)
- constraints.yml: `execution.constraints_finalization_gate`

Inputs:
- Constraints config from TASK-003
- Current workflow state

Outputs (artifacts/files created or changed):
- `aiw/workflow/gates.py`
- `tests/test_gates.py`

File scope allowlist:
- aiw/workflow/gates.py
- tests/test_gates.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `check_constraints_gate(config: ConstraintsConfig) -> None` — raises `ConstraintsGateError` on failure.
- Called before `aiw decompose` and `aiw go`.
- Checks `quality.test_command` is non-placeholder.
- Checks git repo accessible.

Constraints enforced:
- `execution.constraints_finalization_gate.enabled`
- `execution.constraints_finalization_gate.required_non_placeholder_fields`
- `execution.constraints_finalization_gate.placeholder_values`
- `execution.constraints_finalization_gate.refuse_commands`

Non-goals:
- No command routing (done in TASK-021).

Acceptance criteria (measurable):
- Valid constraints.yml passes gate.
- Missing `quality.test_command` fails gate.
- `test_command: "TBD"` fails gate.
- `test_command: ""` fails gate.
- Emit `constraint_validation_failed` event data on failure.
- No partial artifacts written on failure.

Tests / checks required:
- `pytest tests/test_gates.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Returns structured error for `constraint_validation_failed` trace event.

Rollback plan:
- `git checkout` to pre-task baseline.
