## TASK-006: Spec-phase draft commands (prd/sdd/adrs/constraints)

Type: IMPLEMENTATION
Depends_on: [TASK-004, TASK-005]

Objective:
Implement the 4 spec-phase draft commands that transition the workflow into DRAFT states for each artifact type.

Context (spec refs):
- PRD §5.2 (command allowance by state)
- SDD §4.1 (spec-phase AI — single-pass)
- constraints.yml: `workflow.allowed_commands_by_state`, `workflow.transitions`

Inputs:
- State machine (TASK-002)

Outputs (artifacts/files created or changed):
- `aiw/cli/spec_cmds.py`
- `aiw/orchestrator/spec_phase.py`
- `aiw/orchestrator/__init__.py` (updated)
- `tests/test_spec_draft_cmds.py`

File scope allowlist:
- aiw/cli/spec_cmds.py
- aiw/orchestrator/spec_phase.py
- aiw/orchestrator/__init__.py
- tests/test_spec_draft_cmds.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `aiw prd`: INIT → PRD_DRAFT
- `aiw sdd`: PRD_APPROVED → SDD_DRAFT
- `aiw adrs`: SDD_APPROVED → ADRS_DRAFT
- `aiw constraints`: ADRS_APPROVED → CONSTRAINTS_DRAFT
- Each may spawn a single-pass AI session scoped to the target artifact (stub acceptable).

Constraints enforced:
- `workflow.allowed_commands_by_state`
- `workflow.illegal_actions_must_fail_hard`

Non-goals:
- No approve commands (done in TASK-025).
- No artifact locking trigger (approval triggers locks).
- No CLI router (done in TASK-021).

Acceptance criteria (measurable):
- `aiw prd` in INIT → PRD_DRAFT.
- `aiw sdd` in PRD_APPROVED → SDD_DRAFT.
- `aiw adrs` in SDD_APPROVED → ADRS_DRAFT.
- `aiw constraints` in ADRS_APPROVED → CONSTRAINTS_DRAFT.
- Each command rejected in wrong state.

Tests / checks required:
- `pytest tests/test_spec_draft_cmds.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- State transitions logged.

Rollback plan:
- `git checkout` to pre-task baseline.
