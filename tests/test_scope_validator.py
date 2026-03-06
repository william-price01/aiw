"""Tests for task write-scope and diff-size validation."""

from __future__ import annotations

from pathlib import Path

from aiw.infra import ConstraintsConfig, load_constraints
from aiw.tasks.scope_validator import validate_diff_size, validate_scope


def test_validate_scope_allows_files_in_task_allowlist() -> None:
    violations = validate_scope(
        changed_files=["aiw/tasks/scope_validator.py", "tests/test_scope_validator.py"],
        task_allowlist=_task_allowlist(),
        constraints=_load_constraints(),
    )

    assert violations == []


def test_validate_scope_flags_files_outside_task_allowlist() -> None:
    violations = validate_scope(
        changed_files=["aiw/workflow/state_machine.py"],
        task_allowlist=_task_allowlist(),
        constraints=_load_constraints(),
    )

    assert violations == ["outside_task_allowlist:aiw/workflow/state_machine.py"]


def test_validate_scope_rejects_internal_tool_state_paths() -> None:
    violations = validate_scope(
        changed_files=[".aiw/workflow_state.json"],
        task_allowlist=_task_allowlist(),
        constraints=_load_constraints(),
    )

    assert violations == ["forbidden_path:.aiw/workflow_state.json"]


def test_validate_scope_flags_paths_outside_global_allowlist() -> None:
    violations = validate_scope(
        changed_files=["README.md"],
        task_allowlist=_task_allowlist(),
        constraints=_load_constraints(),
    )

    assert violations == ["outside_global_allowlist:README.md"]


def test_validate_diff_size_allows_changes_within_thresholds() -> None:
    violations = validate_diff_size(
        files_changed=30,
        lines_changed=1500,
        constraints=_load_constraints(),
    )

    assert violations == []


def test_validate_diff_size_rejects_file_count_over_threshold() -> None:
    violations = validate_diff_size(
        files_changed=31,
        lines_changed=1500,
        constraints=_load_constraints(),
    )

    assert violations == ["max_files_changed_exceeded:31>30"]


def test_validate_diff_size_rejects_line_count_over_threshold() -> None:
    violations = validate_diff_size(
        files_changed=30,
        lines_changed=1501,
        constraints=_load_constraints(),
    )

    assert violations == ["max_lines_changed_exceeded:1501>1500"]


def test_validate_diff_size_returns_both_violations_when_both_thresholds_exceeded() -> (
    None
):
    violations = validate_diff_size(
        files_changed=31,
        lines_changed=1501,
        constraints=_load_constraints(),
    )

    assert violations == [
        "max_files_changed_exceeded:31>30",
        "max_lines_changed_exceeded:1501>1500",
    ]


def _load_constraints() -> ConstraintsConfig:
    return load_constraints(Path("docs/constraints.yml"))


def _task_allowlist() -> list[str]:
    return ["aiw/tasks/scope_validator.py", "tests/test_scope_validator.py"]
