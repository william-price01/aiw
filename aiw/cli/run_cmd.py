"""CLI entry point wrapper for `aiw run`."""
from __future__ import annotations

from pathlib import Path

from aiw.orchestrator.dag_executor import DagRunResult, run_dag


def run(root: Path, resume: bool = False) -> DagRunResult:
    """Run or resume the DAG executor."""
    return run_dag(root, resume=resume)
