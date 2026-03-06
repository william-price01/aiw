"""CLI entry points for change request handling."""

from __future__ import annotations

from pathlib import Path

from aiw.workflow.change_request import request_change_for_repo


def request_change(root: Path, target: str, reason: str, impact: str) -> Path:
    """Create a change request and apply the required re-approval rollback."""
    return request_change_for_repo(
        root=root,
        target=target,
        reason=reason,
        impact=impact,
    )
