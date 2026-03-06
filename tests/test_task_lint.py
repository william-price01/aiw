"""Tests for task preflight lint validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from aiw.infra import ConstraintsConfig, load_constraints
from aiw.tasks import TaskLintError, check_task_lint, lint_task


def test_lint_task_accepts_valid_task_file() -> None:
    errors = lint_task(Path("docs/tasks/TASK-009.md"), _load_constraints())

    assert errors == []


def test_lint_task_detects_missing_acceptance_criteria(tmp_path: Path) -> None:
    task_path = _write_task(
        tmp_path,
        """
## TASK-999: Example

Type: IMPLEMENTATION
Depends_on: []

Objective:
Do one thing.

File scope allowlist:
- aiw/tasks/lint.py

Non-goals:
- No unrelated edits.

Tests / checks required:
- pytest tests/test_task_lint.py -q
""",
    )

    assert lint_task(task_path, _load_constraints()) == [
        "Missing required field: Acceptance criteria"
    ]


def test_lint_task_detects_missing_tests(tmp_path: Path) -> None:
    task_path = _write_task(
        tmp_path,
        """
## TASK-999: Example

Type: IMPLEMENTATION
Depends_on: []

Objective:
Do one thing.

File scope allowlist:
- aiw/tasks/lint.py

Non-goals:
- No unrelated edits.

Acceptance criteria (measurable):
- Works.
""",
    )

    assert lint_task(task_path, _load_constraints()) == [
        "Missing required field: Tests / checks required"
    ]


def test_lint_task_detects_missing_file_scope(tmp_path: Path) -> None:
    task_path = _write_task(
        tmp_path,
        """
## TASK-999: Example

Type: IMPLEMENTATION
Depends_on: []

Objective:
Do one thing.

Non-goals:
- No unrelated edits.

Acceptance criteria (measurable):
- Works.

Tests / checks required:
- pytest tests/test_task_lint.py -q
""",
    )

    assert lint_task(task_path, _load_constraints()) == [
        "Missing required field: File scope allowlist"
    ]


def test_lint_task_detects_missing_non_goals(tmp_path: Path) -> None:
    task_path = _write_task(
        tmp_path,
        """
## TASK-999: Example

Type: IMPLEMENTATION
Depends_on: []

Objective:
Do one thing.

File scope allowlist:
- aiw/tasks/lint.py

Acceptance criteria (measurable):
- Works.

Tests / checks required:
- pytest tests/test_task_lint.py -q
""",
    )

    assert lint_task(task_path, _load_constraints()) == [
        "Missing required field: Non-goals"
    ]


def test_lint_task_rejects_forbidden_file_scope_path(tmp_path: Path) -> None:
    task_path = _write_task(
        tmp_path,
        """
## TASK-999: Example

Type: IMPLEMENTATION
Depends_on: []

Objective:
Do one thing.

File scope allowlist:
- .aiw/workflow_state.json

Non-goals:
- No unrelated edits.

Acceptance criteria (measurable):
- Works.

Tests / checks required:
- pytest tests/test_task_lint.py -q
""",
    )

    assert lint_task(task_path, _load_constraints()) == [
        "Forbidden file scope path: .aiw/workflow_state.json"
    ]


def test_check_task_lint_exposes_structured_failure_event(tmp_path: Path) -> None:
    task_path = _write_task(
        tmp_path,
        """
## TASK-999: Example

Type: IMPLEMENTATION
Depends_on: []

Objective:
Do one thing.

File scope allowlist:
- .aiw/workflow_state.json

Acceptance criteria (measurable):
- Works.

Tests / checks required:
- pytest tests/test_task_lint.py -q
""",
    )

    with pytest.raises(TaskLintError) as exc_info:
        check_task_lint(task_path, _load_constraints())

    assert exc_info.value.errors == (
        "Missing required field: Non-goals",
        "Forbidden file scope path: .aiw/workflow_state.json",
    )
    assert exc_info.value.event.event_type == "task_lint_failed"
    assert exc_info.value.event.payload == {
        "task_path": task_path.as_posix(),
        "errors": [
            "Missing required field: Non-goals",
            "Forbidden file scope path: .aiw/workflow_state.json",
        ],
    }


def _load_constraints() -> ConstraintsConfig:
    return load_constraints(Path("docs/constraints.yml"))


def _write_task(tmp_path: Path, content: str) -> Path:
    task_path = tmp_path / "TASK-999.md"
    task_path.write_text(content.lstrip(), encoding="utf-8")
    return task_path
