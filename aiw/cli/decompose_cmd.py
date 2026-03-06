"""CLI entry point wrapper for `aiw decompose`."""

from __future__ import annotations

from pathlib import Path

from aiw.orchestrator.decompose import DecomposeResult, run_decompose


def decompose(root: Path) -> DecomposeResult:
    """Run the decompose orchestration flow."""
    return run_decompose(root)
