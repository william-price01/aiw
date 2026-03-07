"""CLI entry point wrapper for `aiw go`."""

from __future__ import annotations

from pathlib import Path

from aiw.orchestrator.executor import ExecutionResult, execute_task


def go(root: Path, task_id: str) -> ExecutionResult:
    """Run the happy-path task executor."""
    return execute_task(task_id, root)
