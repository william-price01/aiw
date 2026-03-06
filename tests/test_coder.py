"""Tests for bounded Coder session integration."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aiw.infra import ConstraintsConfig, load_constraints
from aiw.orchestrator.coder import PatchValidationError, TaskSpec, run_coder_session


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


def test_task_spec_from_file_extracts_task_id_and_allowlist(tmp_path: Path) -> None:
    task_path = tmp_path / "TASK-013.md"
    task_path.write_text(
        """## TASK-013: Example

File scope allowlist:
- aiw/orchestrator/coder.py
- tests/test_coder.py
""",
        encoding="utf-8",
    )

    task_spec = TaskSpec.from_file(task_path)

    assert task_spec.task_id == "TASK-013"
    assert task_spec.file_scope_allowlist == (
        "aiw/orchestrator/coder.py",
        "tests/test_coder.py",
    )


def test_run_coder_session_invokes_codex_once_and_returns_patch_result(
    git_repo: Path,
) -> None:
    task_spec = TaskSpec(
        task_id="TASK-013",
        path=Path("docs/tasks/TASK-013.md"),
        content="Objective:\nImplement the coder session.\n",
        file_scope_allowlist=("aiw/example.py",),
    )
    constraints = _load_constraints()
    calls: list[tuple[Path, str]] = []

    def codex_runner(workspace: Path, prompt: str) -> None:
        calls.append((workspace, prompt))
        target = workspace / "aiw" / "example.py"
        target.write_text("VALUE = 2\n", encoding="utf-8")

    result = run_coder_session(
        task_spec,
        constraints,
        repo_root=git_repo,
        codex_runner=codex_runner,
    )

    assert len(calls) == 1
    assert task_spec.content in calls[0][1]
    assert "aiw/example.py" in calls[0][1]
    assert result.changed_files == ("aiw/example.py",)
    assert result.diff_stats.files_changed == 1
    assert result.diff_stats.lines_changed == 2
    assert result.success is True
    assert "diff --git a/aiw/example.py b/aiw/example.py" in result.patch
    assert (git_repo / "aiw" / "example.py").read_text(encoding="utf-8") == (
        "VALUE = 1\n"
    )


def test_run_coder_session_rejects_patch_outside_task_allowlist(git_repo: Path) -> None:
    task_spec = TaskSpec(
        task_id="TASK-013",
        path=Path("docs/tasks/TASK-013.md"),
        content="Objective:\nImplement the coder session.\n",
        file_scope_allowlist=("aiw/example.py",),
    )

    def codex_runner(workspace: Path, prompt: str) -> None:
        del prompt
        forbidden = workspace / "tests" / "test_extra.py"
        forbidden.parent.mkdir(parents=True, exist_ok=True)
        forbidden.write_text("def test_extra():\n    assert True\n", encoding="utf-8")

    with pytest.raises(PatchValidationError) as exc_info:
        run_coder_session(
            task_spec,
            _load_constraints(),
            repo_root=git_repo,
            codex_runner=codex_runner,
        )

    assert exc_info.value.scope_violations == (
        "outside_task_allowlist:tests/test_extra.py",
    )


def test_run_coder_session_rejects_internal_tool_state_writes(git_repo: Path) -> None:
    task_spec = TaskSpec(
        task_id="TASK-013",
        path=Path("docs/tasks/TASK-013.md"),
        content="Objective:\nImplement the coder session.\n",
        file_scope_allowlist=("aiw/example.py",),
    )

    def codex_runner(workspace: Path, prompt: str) -> None:
        del prompt
        forbidden = workspace / ".aiw" / "run.json"
        forbidden.parent.mkdir(parents=True, exist_ok=True)
        forbidden.write_text("{\"run_id\": \"123\"}\n", encoding="utf-8")

    with pytest.raises(PatchValidationError) as exc_info:
        run_coder_session(
            task_spec,
            _load_constraints(),
            repo_root=git_repo,
            codex_runner=codex_runner,
        )

    assert exc_info.value.scope_violations == ("forbidden_path:.aiw/run.json",)


def _load_constraints() -> ConstraintsConfig:
    return load_constraints(Path("docs/constraints.yml"))
