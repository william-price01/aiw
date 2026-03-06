"""Tests for artifact locking rules and lock violation checks."""

from __future__ import annotations

import subprocess

import pytest

from aiw.workflow.locking import (
    GIT_DIFF_NAME_ONLY_COMMAND,
    LockViolationError,
    check_lock_violations,
    enforce_lock_rules,
    get_changed_files_via_git_diff_name_only,
    get_locked_paths,
)


@pytest.mark.parametrize(
    ("state", "expected_locked_path"),
    [
        ("PRD_APPROVED", "docs/prd.md"),
        ("SDD_APPROVED", "docs/sdd.md"),
        ("ADRS_APPROVED", "docs/adrs/**"),
        ("CONSTRAINTS_APPROVED", "docs/constraints.yml"),
    ],
)
def test_get_locked_paths_after_approval_states_include_expected_artifacts(
    state: str,
    expected_locked_path: str,
) -> None:
    assert expected_locked_path in get_locked_paths(state)


def test_get_locked_paths_during_executing_include_immutable_planning_artifacts() -> (
    None
):
    locked = get_locked_paths("EXECUTING")

    assert "docs/tasks/DAG.md" in locked
    assert "docs/tasks/DAG.yml" in locked
    assert "docs/tasks/TASK-???.md" in locked


def test_check_lock_violations_returns_matching_changed_files() -> None:
    changed_files = [
        "docs/tasks/TASK-001.md",
        "docs/prd.md",
        "docs/tasks/COMPLETED.md",
        "aiw/workflow/state_machine.py",
        "docs/adrs/ADR-001.md",
    ]

    violations = check_lock_violations("EXECUTING", changed_files)

    assert violations == [
        "docs/adrs/ADR-001.md",
        "docs/prd.md",
        "docs/tasks/TASK-001.md",
    ]


def test_get_changed_files_uses_git_diff_name_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_command: tuple[str, ...] | None = None

    def fake_run(
        command: tuple[str, ...],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal observed_command
        observed_command = command
        assert check is True
        assert capture_output is True
        assert text is True
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="docs/prd.md\ndocs/tasks/TASK-004.md\n",
        )

    monkeypatch.setattr("aiw.workflow.locking.subprocess.run", fake_run)

    changed_files = get_changed_files_via_git_diff_name_only()

    assert observed_command == GIT_DIFF_NAME_ONLY_COMMAND
    assert changed_files == ["docs/prd.md", "docs/tasks/TASK-004.md"]


def test_enforce_lock_rules_raises_lock_violation_error() -> None:
    with pytest.raises(LockViolationError) as exc_info:
        enforce_lock_rules("EXECUTING", ["docs/tasks/TASK-004.md"])

    assert exc_info.value.violations == ("docs/tasks/TASK-004.md",)
