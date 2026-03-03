## TASK-025: Spec-phase approve commands (approve-prd/sdd/adrs/constraints)

Type: IMPLEMENTATION
Depends_on: [TASK-006]

Objective:
Implement the 4 approve commands that transition DRAFT → APPROVED states and trigger artifact locking for each approved artifact.

Context (spec refs):
- PRD §5.2 (command allowance by state), §5.3 (locking rules)
- constraints.yml: `workflow.transitions`, `boundaries.locked_artifacts.lock_after_state`

Inputs:
- State machine (TASK-002)
- Locking engine (TASK-004)
- Draft commands infrastructure (TASK-006)

Outputs (artifacts/files created or changed):
- `aiw/cli/spec_cmds.py` (extended)
- `aiw/orchestrator/spec_phase.py` (extended)
- `tests/test_spec_approve_cmds.py`

File scope allowlist:
- aiw/cli/spec_cmds.py
- aiw/orchestrator/spec_phase.py
- tests/test_spec_approve_cmds.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `aiw approve-prd`: PRD_DRAFT → PRD_APPROVED; locks docs/prd.md.
- `aiw approve-sdd`: SDD_DRAFT → SDD_APPROVED; locks docs/sdd.md.
- `aiw approve-adrs`: ADRS_DRAFT → ADRS_APPROVED; locks docs/adrs/**.
- `aiw approve-constraints`: CONSTRAINTS_DRAFT → CONSTRAINTS_APPROVED; locks docs/constraints.yml.

Constraints enforced:
- `workflow.allowed_commands_by_state`
- `workflow.illegal_actions_must_fail_hard`
- `boundaries.locked_artifacts.lock_after_state`

Non-goals:
- No draft commands (done in TASK-006).
- No CLI router (done in TASK-021).

Acceptance criteria (measurable):
- `aiw approve-prd` in PRD_DRAFT → PRD_APPROVED; prd.md in locked set.
- `aiw approve-sdd` in SDD_DRAFT → SDD_APPROVED; sdd.md in locked set.
- `aiw approve-adrs` in ADRS_DRAFT → ADRS_APPROVED; adrs/** in locked set.
- `aiw approve-constraints` in CONSTRAINTS_DRAFT → CONSTRAINTS_APPROVED; constraints.yml in locked set.
- Each command rejected in wrong state.

Tests / checks required:
- `pytest tests/test_spec_approve_cmds.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- State transitions logged.

Rollback plan:
- `git checkout` to pre-task baseline.
