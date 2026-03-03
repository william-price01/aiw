## TASK-002: Workflow state machine (core)

Type: IMPLEMENTATION
Depends_on: [TASK-001]

Objective:
Implement the core workflow state machine with all 12 states, valid transitions, state persistence to `.aiw/workflow_state.json`, and hard failure on invalid transitions.

Context (spec refs):
- PRD §5 (workflow state machine — authoritative)
- SDD §5 (global workflow state machine)
- constraints.yml: `workflow.states`, `workflow.transitions`, `workflow.enforce_state_machine`, `workflow.illegal_actions_must_fail_hard`

Inputs:
- State list and transition table from PRD §5.2 and constraints.yml `workflow.transitions`

Outputs (artifacts/files created or changed):
- `aiw/workflow/state_machine.py`
- `aiw/workflow/__init__.py` (updated)
- `tests/test_state_machine.py`

File scope allowlist:
- aiw/workflow/state_machine.py
- aiw/workflow/__init__.py
- tests/test_state_machine.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `WorkflowStateMachine` class with:
  - `current_state -> str`
  - `transition(command: str) -> str` (returns new state or raises)
  - `load(path: Path) -> WorkflowStateMachine`
  - `save(path: Path) -> None`
- Invalid transitions raise `IllegalStateTransitionError`.

Constraints enforced:
- `workflow.enforce_state_machine`: true
- `workflow.illegal_actions_must_fail_hard`: true
- `workflow.state_transitions_must_be_logged`: true

Non-goals:
- No CLI integration (done in TASK-005/006).
- No trace event emission (done in TASK-010).
- No locking logic (done in TASK-004).

Acceptance criteria (measurable):
- All 12 states represented in code.
- All transitions from constraints.yml `workflow.transitions` succeed.
- Any transition not in the table raises `IllegalStateTransitionError`.
- State round-trips through JSON file.
- 100% of transitions tested.

Tests / checks required:
- `pytest tests/test_state_machine.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- State machine logs transitions (print or logging module). Structured trace integration deferred to TASK-010.

Rollback plan:
- `git checkout` to pre-task baseline.
