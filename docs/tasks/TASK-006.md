## TASK-006: Spec-phase draft commands (prd/sdd/adrs/constraints)

Type: IMPLEMENTATION
Depends_on: [TASK-004, TASK-005]

Objective:
Implement the 4 spec-phase draft commands that transition the workflow into DRAFT states and establish the active draft artifact scope for collaborative human ↔ AI revision.

Context (spec refs):
- PRD §5.2 (command allowance by state), §5.5 (AI mediation across phases)
- SDD §4.1 (spec-phase AI — interactive drafting, artifact-scoped)
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
- `aiw prd`: INIT → PRD_DRAFT; active editable artifact = `docs/prd.md`.
- `aiw sdd`: PRD_APPROVED → SDD_DRAFT; active editable artifact = `docs/sdd.md`.
- `aiw adrs`: SDD_APPROVED → ADRS_DRAFT; active editable artifact = `docs/adrs/**`.
- `aiw constraints`: ADRS_APPROVED → CONSTRAINTS_DRAFT; active editable artifact = `docs/constraints.yml`.
- Entering a DRAFT state enables collaborative human ↔ AI drafting within the active artifact scope.
- Drafting may continue across multiple turns until explicit human approval.
- Draft commands do not auto-approve and do not auto-transition to the next phase.

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
- Each DRAFT command establishes the correct active artifact scope and does not permit edits outside that scope.

Tests / checks required:
- `pytest tests/test_spec_draft_cmds.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- State transitions logged.

Rollback plan:
- `git checkout` to pre-task baseline.
