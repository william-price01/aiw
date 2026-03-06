"""Tests for bounded Fixer session integration."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aiw.infra import ConstraintsConfig, load_constraints
from aiw.orchestrator.coder import PatchValidationError, TaskSpec
from aiw.orchestrator.fixer import (
    build_fixer_spawned_event_data,
    run_fixer_session,
)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    subprocess.run(
        ("git", "init"),
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ("git", "config", "user.name", "AIW Tests"),
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ("git", "config", "user.email", "aiw-tests@example.com"),
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    tracked = tmp_path / "aiw" / "example.py"
    tracked.parent.mkdir(parents=True, exist_ok=True)
    tracked.write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(
        ("git", "add", "aiw/example.py"),
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ("git", "commit", "-m", "seed"),
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    return tmp_path


def test_run_fixer_session_requires_failed_test_output(git_repo: Path) -> None:
    task_spec = TaskSpec(
        task_id="TASK-014",
        path=Path("docs/tasks/TASK-014.md"),
        content="Objective:\nImplement the fixer session.\n",
        file_scope_allowlist=("aiw/example.py",),
    )

    with pytest.raises(
        ValueError, match="fixer session may only spawn after a failed test run"
    ):
        run_fixer_session(
            task_spec,
            (
                "============================== 1 passed in 0.01s "
                "=============================="
            ),
            _load_constraints(),
            repo_root=git_repo,
        )


def test_run_fixer_session_invokes_codex_once_and_returns_patch_result(
    git_repo: Path,
) -> None:
    task_spec = TaskSpec(
        task_id="TASK-014",
        path=Path("docs/tasks/TASK-014.md"),
        content="Objective:\nImplement the fixer session.\n",
        file_scope_allowlist=("aiw/example.py",),
    )
    failed_output = (
        "============================== 1 failed in 0.01s "
        "=============================="
    )
    constraints = _load_constraints()
    calls: list[tuple[Path, str]] = []

    def codex_runner(workspace: Path, prompt: str) -> None:
        calls.append((workspace, prompt))
        target = workspace / "aiw" / "example.py"
        target.write_text("VALUE = 2\n", encoding="utf-8")

    result = run_fixer_session(
        task_spec,
        failed_output,
        constraints,
        repo_root=git_repo,
        codex_runner=codex_runner,
    )

    assert len(calls) == 1
    assert failed_output in calls[0][1]
    assert "aiw/example.py" in calls[0][1]
    assert result.changed_files == ("aiw/example.py",)
    assert result.diff_stats.files_changed == 1
    assert result.diff_stats.lines_changed == 2
    assert result.success is True
    assert "diff --git a/aiw/example.py b/aiw/example.py" in result.patch
    assert (git_repo / "aiw" / "example.py").read_text(encoding="utf-8") == (
        "VALUE = 1\n"
    )


def test_run_fixer_session_rejects_patch_outside_task_allowlist(git_repo: Path) -> None:
    task_spec = TaskSpec(
        task_id="TASK-014",
        path=Path("docs/tasks/TASK-014.md"),
        content="Objective:\nImplement the fixer session.\n",
        file_scope_allowlist=("aiw/example.py",),
    )

    def codex_runner(workspace: Path, prompt: str) -> None:
        del prompt
        forbidden = workspace / "tests" / "test_extra.py"
        forbidden.parent.mkdir(parents=True, exist_ok=True)
        forbidden.write_text("def test_extra():\n    assert True\n", encoding="utf-8")

    with pytest.raises(PatchValidationError) as exc_info:
        run_fixer_session(
            task_spec,
            "FAILED tests/test_example.py::test_value - assert 1 == 2",
            _load_constraints(),
            repo_root=git_repo,
            codex_runner=codex_runner,
        )

    assert exc_info.value.scope_violations == (
        "outside_task_allowlist:tests/test_extra.py",
    )


def test_build_fixer_spawned_event_data_returns_trace_payload() -> None:
    task_spec = TaskSpec(
        task_id="TASK-014",
        path=Path("docs/tasks/TASK-014.md"),
        content="Objective:\nImplement the fixer session.\n",
        file_scope_allowlist=("aiw/orchestrator/fixer.py", "tests/test_fixer.py"),
    )

    payload = build_fixer_spawned_event_data(
        task_spec,
        "FAILED tests/test_fixer.py::test_run_fixer_session - AssertionError",
        _load_constraints(),
    )

    assert payload["task_id"] == "TASK-014"
    assert payload["trigger"] == "test_failed"
    assert payload["write_scope_allowlist"] == [
        "aiw/orchestrator/fixer.py",
        "tests/test_fixer.py",
    ]
    assert payload["max_iterations_per_task"] == 3
    assert "FAILED tests/test_fixer.py" in str(payload["failed_test_output_excerpt"])


def _load_constraints() -> ConstraintsConfig:
    return load_constraints(Path("docs/constraints.yml"))
