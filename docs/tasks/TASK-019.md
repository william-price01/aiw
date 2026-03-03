## TASK-019: Change request flow

Type: IMPLEMENTATION
Depends_on: [TASK-004, TASK-025]

Objective:
Implement `aiw request-change` command that creates a change request file and supports re-approval transitions for locked artifacts.

Context (spec refs):
- PRD §5.4 (change request mechanism)
- constraints.yml: `boundaries.change_request`

Inputs:
- Target artifact, reason, impact (user-provided)
- Current workflow state

Outputs (artifacts/files created or changed):
- `aiw/cli/change_request_cmd.py`
- `aiw/workflow/change_request.py`
- `tests/test_change_request.py`
- Runtime: `docs/requests/CHANGE_REQUEST.md`

File scope allowlist:
- aiw/cli/change_request_cmd.py
- aiw/workflow/change_request.py
- tests/test_change_request.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `create_change_request(target: str, reason: str, impact: str, output_path: Path) -> Path`
- `apply_change_request(request: ChangeRequest, state_machine: WorkflowStateMachine) -> None`
  — transitions locked artifact's state back to DRAFT.
- Re-approval commands: `aiw approve-prd`, `aiw approve-sdd`, etc.

Constraints enforced:
- `boundaries.change_request.file`: `docs/requests/CHANGE_REQUEST.md`
- `boundaries.change_request.required_for_modifying_locked_artifacts`
- `boundaries.change_request.requires_reapproval_transition`

Non-goals:
- No automatic re-approval.
- No modification of locked artifacts directly.

Acceptance criteria (measurable):
- `aiw request-change` creates `docs/requests/CHANGE_REQUEST.md`.
- File contains: target artifact, reason, impact.
- Applying request transitions PRD_APPROVED→PRD_DRAFT (etc.).
- `aiw request-change` allowed from: PRD_APPROVED, SDD_APPROVED, ADRS_APPROVED, CONSTRAINTS_APPROVED, PLANNED, BLOCKED.
- Re-approval required after change.

Tests / checks required:
- `pytest tests/test_change_request.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- State transition logged.

Rollback plan:
- `git checkout` to pre-task baseline.
