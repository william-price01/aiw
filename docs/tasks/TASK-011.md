## TASK-011: Checkpointing (git-based)

Type: IMPLEMENTATION
Depends_on: [TASK-002]

Objective:
Implement deterministic git-based checkpointing: create checkpoint commits before EXECUTING entry and after each applied patch, and support revert to any checkpoint.

Context (spec refs):
- PRD §7.4 (deterministic artifacts), SDD §13 (checkpointing / undo / reset)

Inputs:
- Git repository state

Outputs (artifacts/files created or changed):
- `aiw/infra/checkpoint.py`
- `tests/test_checkpoint.py`

File scope allowlist:
- aiw/infra/checkpoint.py
- tests/test_checkpoint.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `create_checkpoint(label: str) -> str` — creates git commit, returns ref.
- `revert_to_checkpoint(ref: str) -> None` — resets working tree to checkpoint.
- `get_baseline_ref(task_id: str) -> str` — returns pre-task baseline ref.
- Checkpoint commits use deterministic message format: `[aiw-checkpoint] <label>`.

Constraints enforced:
- Git diff is the source of truth (PRD §7.4).

Non-goals:
- No undo/reset CLI commands (done in TASK-017).
- No execution loop integration (done in TASK-015).

Acceptance criteria (measurable):
- `create_checkpoint` creates a git commit.
- `revert_to_checkpoint` restores working tree exactly.
- Baseline ref retrievable by task ID.
- Deterministic checkpoint labels.

Tests / checks required:
- `pytest tests/test_checkpoint.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- None (git history is the trace).

Rollback plan:
- `git checkout` to pre-task baseline.
