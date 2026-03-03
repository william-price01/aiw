## TASK-005: `aiw init` command

Type: IMPLEMENTATION
Depends_on: [TASK-002]

Objective:
Implement the `aiw init` command that creates the minimum internal tool state directory and initializes workflow state.

Context (spec refs):
- PRD §5.1 (INIT state), §5.2 (command allowance)
- SDD §2 (authoritative aiw init scaffold)

Inputs:
- None (runs in a git repo root)

Outputs (artifacts/files created or changed):
- `aiw/cli/init_cmd.py`
- `aiw/cli/__init__.py` (updated)
- `tests/test_init.py`
- Runtime: `.aiw/`, `.aiw/workflow_state.json`, `.aiw/runs/`

File scope allowlist:
- aiw/cli/init_cmd.py
- aiw/cli/__init__.py
- tests/test_init.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `init_project(root: Path) -> None`
- Creates `.aiw/workflow_state.json` with `{"state": "INIT"}`.
- Creates `.aiw/runs/` directory.
- Idempotent: re-running does not corrupt existing state.

Constraints enforced:
- `boundaries.internal_tool_state.paths`: `.aiw/**`
- `workflow.state_file`: `.aiw/workflow_state.json`

Non-goals:
- No user-facing artifact creation (docs/ structure is user-authored).
- No CLI router (done in TASK-021).

Acceptance criteria (measurable):
- `.aiw/` directory created.
- `.aiw/workflow_state.json` exists with `state: INIT`.
- `.aiw/runs/` directory exists.
- Second run does not overwrite existing state.
- Works in a git repo.

Tests / checks required:
- `pytest tests/test_init.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- None.

Rollback plan:
- `git checkout` to pre-task baseline; `rm -rf .aiw`.
