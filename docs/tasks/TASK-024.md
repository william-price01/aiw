## TASK-024: TUI rendering model

Type: IMPLEMENTATION
Depends_on: [TASK-028]

Objective:
Implement a read-only TUI that derives its display strictly from workflow state, task artifacts, and run trace events — with no speculative UI state.

Context (spec refs):
- PRD §15 (TUI rendering model)

Inputs:
- `.aiw/workflow_state.json`
- `docs/tasks/` artifacts
- `.aiw/runs/run-<timestamp>.jsonl` trace events

Outputs (artifacts/files created or changed):
- `aiw/cli/tui.py`
- `tests/test_tui.py`

File scope allowlist:
- aiw/cli/tui.py
- tests/test_tui.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `render_status(root: Path) -> str` — renders current workflow status.
- `render_task_list(root: Path) -> str` — renders task list with statuses.
- `render_run_trace(run_path: Path) -> str` — renders trace events.
- All rendering is read-only; never mutates state.

Constraints enforced:
- TUI derives from state, artifacts, and traces only (PRD §15).

Non-goals:
- No interactive TUI (read-only display for MVP).
- No state mutation from TUI.

Acceptance criteria (measurable):
- Displays current workflow state correctly.
- Displays task list with status derived from artifacts.
- Displays trace events from JSONL.
- No speculative state (only what exists on disk).
- Read-only: no state files modified.

Tests / checks required:
- `pytest tests/test_tui.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- TUI consumes observability data; does not produce it.

Rollback plan:
- `git checkout` to pre-task baseline.
