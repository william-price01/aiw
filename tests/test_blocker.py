"""Tests for blocker report generation."""

from __future__ import annotations

from pathlib import Path

from aiw.infra.trace import REQUIRED_TRACE_EVENTS
from aiw.orchestrator.blocker import (
    BlockerContext,
    generate_blocker_report,
    generate_followup_tasks,
    generate_scope_expansion_request,
)


def test_generate_blocker_report_writes_required_fields(tmp_path: Path) -> None:
    context = BlockerContext(
        root=tmp_path,
        iterations_used=3,
        last_test_output="1 failed, 2 passed",
        failure_reason="iteration_exhausted",
    )

    report_path = generate_blocker_report("TASK-016", context)

    assert report_path == tmp_path / "docs" / "reports" / "TASK-016_blocker_report.md"
    contents = report_path.read_text(encoding="utf-8")
    assert "- Task ID: TASK-016" in contents
    assert "- Iterations used: 3" in contents
    assert "- Failure reason: iteration_exhausted" in contents
    assert "1 failed, 2 passed" in contents


def test_generate_optional_reports_only_when_requested(tmp_path: Path) -> None:
    context = BlockerContext(
        root=tmp_path,
        iterations_used=3,
        last_test_output="2 failed",
        failure_reason="task_too_large",
        followup_tasks=(
            "Create a smaller task for parser updates.",
            "Create a smaller task for validation tests.",
        ),
        scope_expansion_request=(
            "Fix requires editing files outside the task allowlist."
        ),
    )

    followup_path = generate_followup_tasks("TASK-016", context)
    scope_path = generate_scope_expansion_request("TASK-016", context)

    assert followup_path == tmp_path / "docs" / "reports" / "TASK-016_followup_tasks.md"
    assert scope_path == (
        tmp_path / "docs" / "reports" / "TASK-016_scope_expansion_request.md"
    )
    assert "1. Create a smaller task for parser updates." in followup_path.read_text(
        encoding="utf-8"
    )
    assert "- Reason: Fix requires editing files outside the task allowlist." in (
        scope_path.read_text(encoding="utf-8")
    )


def test_generate_optional_reports_returns_none_when_not_applicable(
    tmp_path: Path,
) -> None:
    context = BlockerContext(
        root=tmp_path,
        iterations_used=3,
        last_test_output="3 failed",
        failure_reason="iteration_exhausted",
    )

    assert generate_followup_tasks("TASK-016", context) is None
    assert generate_scope_expansion_request("TASK-016", context) is None
    assert not (tmp_path / "docs" / "reports").exists()


def test_blocked_trace_event_remains_required() -> None:
    assert "blocked" in REQUIRED_TRACE_EVENTS
