## TASK-017: Undo and reset commands

Type: IMPLEMENTATION
Depends_on: [TASK-011, TASK-027]

Objective:
Implement `aiw undo` (revert most recent checkpoint) and `aiw reset TASK-###` (revert to pre-task baseline), both deterministic via git.

Context (spec refs):
- PRD §5.2 (EXECUTING allowed commands: undo, reset)
- SDD §13 (checkpointing / undo / reset)

Inputs:
- Checkpoint refs from TASK-011
- Current workflow state

Outputs (artifacts/files created or changed):
- `aiw/cli/undo_cmd.py`
- `tests/test_undo_reset.py`

File scope allowlist:
- aiw/cli/undo_cmd.py
- tests/test_undo_reset.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `aiw undo` — reverts to most recent checkpoint ref.
- `aiw reset TASK-###` — reverts to pre-task baseline ref.
- Both only allowed during EXECUTING state.
- Both are deterministic git operations.

Constraints enforced:
- `workflow.allowed_commands_by_state.EXECUTING`: [aiw undo, aiw reset TASK-###]

Non-goals:
- No BLOCKED retry (manual, per PRD §14).

Acceptance criteria (measurable):
- `aiw undo` during EXECUTING reverts to last checkpoint.
- `aiw reset TASK-###` during EXECUTING reverts to baseline.
- Both refused outside EXECUTING state.
- Working tree matches checkpoint/baseline after revert.

Tests / checks required:
- `pytest tests/test_undo_reset.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- State transition logged if applicable.

Rollback plan:
- `git checkout` to pre-task baseline.
