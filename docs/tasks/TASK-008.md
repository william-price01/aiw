## TASK-008: Decompose orchestration and atomic write

Type: IMPLEMENTATION
Depends_on: [TASK-007]

Objective:
Implement the `aiw decompose` command orchestration: state validation, constraints gate check, atomic write scaffolding (write to temp dir, rename on success), and state transition to PLANNED.

Context (spec refs):
- PRD §5.2 (CONSTRAINTS_APPROVED → decompose)
- SDD §5.1 (CONSTRAINTS_APPROVED → PLANNED transition)
- constraints.yml: `workflow.transitions`

Inputs:
- Constraints gate (TASK-007)
- Current workflow state

Outputs (artifacts/files created or changed):
- `aiw/cli/decompose_cmd.py`
- `aiw/orchestrator/decompose.py`
- `tests/test_decompose_orchestration.py`

File scope allowlist:
- aiw/cli/decompose_cmd.py
- aiw/orchestrator/decompose.py
- tests/test_decompose_orchestration.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `run_decompose(root: Path) -> DecomposeResult`
- Validates state=CONSTRAINTS_APPROVED.
- Passes constraints gate.
- Delegates to AI session (TASK-026) for content generation.
- Writes outputs atomically: temp directory → validate → rename to docs/tasks/.
- On failure: no partial artifacts, state unchanged.
- On success: CONSTRAINTS_APPROVED → PLANNED.

Constraints enforced:
- `workflow.transitions`: CONSTRAINTS_APPROVED → PLANNED
- `execution.constraints_finalization_gate`

Non-goals:
- No AI session invocation (done in TASK-026).
- No output content validation (done in TASK-026).

Acceptance criteria (measurable):
- Refused unless state=CONSTRAINTS_APPROVED.
- Passes constraints gate.
- Atomic write: temp dir used, renamed on success.
- On simulated AI failure: no partial files in docs/tasks/.
- On success: state=PLANNED.

Tests / checks required:
- `pytest tests/test_decompose_orchestration.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- State transition logged.

Rollback plan:
- `git checkout` to pre-task baseline; remove docs/tasks/ outputs.
