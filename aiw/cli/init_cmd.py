"""`aiw init` scaffold creation utilities."""

from __future__ import annotations

from pathlib import Path

from aiw.workflow.state_machine import WorkflowStateMachine


def init_project(root: Path) -> None:
    """Create the minimum internal AIW state scaffold for a repository."""
    aiw_dir = root / ".aiw"
    state_file = aiw_dir / "workflow_state.json"
    runs_dir = aiw_dir / "runs"

    aiw_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    if state_file.exists():
        return

    WorkflowStateMachine(current_state="INIT").save(state_file)
