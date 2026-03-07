"""Tests for happy-path task execution orchestration."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from aiw.cli.go_cmd import go
from aiw.cli.init_cmd import init_project
from aiw.orchestrator.coder import DiffStats, PatchResult
from aiw.orchestrator.executor import ExecutionError
from aiw.workflow.gates import GIT_ACCESS_COMMAND


def test_go_refuses_unless_state_is_planned(tmp_path: Path) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, "CONSTRAINTS_APPROVED")

    with pytest.raises(
        ExecutionError,
        match="task execution requires PLANNED state, found CONSTRAINTS_APPROVED",
    ):
        go(repo_root, "TASK-015")

    state = _read_workflow_state(repo_root)
    assert state["state"] == "CONSTRAINTS_APPROVED"
    assert "metadata" not in state


def test_go_executes_happy_path_and_marks_completion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, "PLANNED")
    checkpoint_calls: list[str] = []

    monkeypatch.setattr(
        "aiw.workflow.gates.subprocess.run",
        _successful_git_gate_run,
    )
    
    def fake_create_checkpoint(label: str) -> str:
        checkpoint_calls.append(label)
        return "checkpoint-ref-123"

    def fake_run_coder_session(
        task_spec: object,
        constraints: object,
        repo_root: Path | None = None,
        codex_runner: object | None = None,
    ) -> PatchResult:
        del task_spec, constraints, repo_root, codex_runner
        return _patch_result()

    monkeypatch.setattr(
        "aiw.orchestrator.executor.create_checkpoint",
        fake_create_checkpoint,
    )
    monkeypatch.setattr(
        "aiw.orchestrator.executor.run_coder_session",
        fake_run_coder_session,
    )
    monkeypatch.setattr(
        "aiw.orchestrator.executor.subprocess.run",
        _successful_executor_run,
    )

    result = go(repo_root, "TASK-015")

    assert result.status == "PASS"
    assert result.iterations_used == 1
    UUID(result.run_id)

    assert checkpoint_calls == ["TASK-015 baseline"]
    state = _read_workflow_state(repo_root)
    assert state["current_state"] == "PLANNED"
    metadata = cast(dict[str, str], state["metadata"])
    assert metadata["run_id"] == result.run_id

    completed = (repo_root / "docs" / "tasks" / "COMPLETED.md").read_text(
        encoding="utf-8"
    )
    assert (
        f"| TASK-015 | {result.run_id} |" in completed
        and "| PASS | Completed by aiw go |" in completed
    )

    trace_path = next((repo_root / ".aiw" / "runs").glob("*.jsonl"))
    events = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    event_types = [event["event_type"] for event in events]
    assert "state_transition" in event_types
    assert "test_run_started" in event_types
    assert "test_run_passed" in event_types
    assert "task_marked_complete" in event_types
    assert "run_complete" in event_types
    assert all(event["run_id"] == result.run_id for event in events)


def test_go_hard_fails_when_coder_patch_touches_locked_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, "PLANNED")
    apply_calls: list[tuple[str, Path]] = []

    monkeypatch.setattr(
        "aiw.workflow.gates.subprocess.run",
        _successful_git_gate_run,
    )
    monkeypatch.setattr(
        "aiw.orchestrator.executor.create_checkpoint",
        lambda label: "checkpoint-ref-123",
    )
    monkeypatch.setattr(
        "aiw.orchestrator.executor.run_coder_session",
        lambda task_spec, constraints, repo_root=None, codex_runner=None: PatchResult(
            changed_files=("docs/tasks/DAG.md",),
            diff_stats=DiffStats(files_changed=1, lines_changed=4),
            success=True,
            patch="diff --git a/docs/tasks/DAG.md b/docs/tasks/DAG.md\n",
        ),
    )
    monkeypatch.setattr(
        "aiw.orchestrator.executor._apply_patch",
        lambda patch, root: apply_calls.append((patch, root)),
    )

    with pytest.raises(ExecutionError, match="Locked artifact modification detected"):
        go(repo_root, "TASK-015")

    assert apply_calls == []

    trace_path = next((repo_root / ".aiw" / "runs").glob("*.jsonl"))
    events = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    event_types = [event["event_type"] for event in events]
    assert "lock_violation_hard_fail" in event_types
    assert "scope_validation" not in event_types
    assert "diff_threshold_check" not in event_types

    violation_event = next(
        event for event in events if event["event_type"] == "lock_violation_hard_fail"
    )
    assert violation_event["payload"] == {
        "task_id": "TASK-015",
        "phase": "coder",
        "violations": ["docs/tasks/DAG.md"],
    }


def _init_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    init_project(repo_root)

    docs_dir = repo_root / "docs"
    tasks_dir = docs_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (docs_dir / "constraints.yml").write_text(
        Path("docs/constraints.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tasks_dir / "COMPLETED.md").write_text(
        Path("docs/tasks/COMPLETED.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tasks_dir / "TASK-015.md").write_text(
        Path("docs/tasks/TASK-015.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tasks_dir / "DAG.md").write_text(
        Path("docs/tasks/DAG.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return repo_root


def _write_workflow_state(repo_root: Path, state: str) -> None:
    state_path = repo_root / ".aiw" / "workflow_state.json"
    state_path.write_text(
        json.dumps(
            {"current_state": state, "state": state},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _read_workflow_state(repo_root: Path) -> dict[str, object]:
    state_path = repo_root / ".aiw" / "workflow_state.json"
    return cast(dict[str, object], json.loads(state_path.read_text(encoding="utf-8")))


def _patch_result() -> PatchResult:
    return PatchResult(
        changed_files=("aiw/orchestrator/executor.py",),
        diff_stats=DiffStats(files_changed=1, lines_changed=12),
        success=True,
        patch="",
    )


def _successful_git_gate_run(
    command: list[str] | tuple[str, ...],
    *,
    check: bool,
    capture_output: bool,
    text: bool,
    cwd: Path | None = None,
    input: str | None = None,
) -> subprocess.CompletedProcess[str]:
    assert tuple(command) == GIT_ACCESS_COMMAND
    assert check is True
    assert capture_output is True
    assert text is True
    assert cwd is None
    assert input is None
    return subprocess.CompletedProcess(args=command, returncode=0, stdout="/tmp/repo\n")


def _successful_executor_run(
    command: list[str] | tuple[str, ...],
    *,
    check: bool,
    capture_output: bool,
    text: bool,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    input: str | None = None,
) -> subprocess.CompletedProcess[str]:
    assert capture_output is True
    assert text is True
    if tuple(command) == GIT_ACCESS_COMMAND:
        assert check is True
        assert cwd is None
        assert env is None
        assert input is None
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="/tmp/repo\n",
        )
    if tuple(command) == ("pytest", "-q"):
        assert check is False
        assert cwd is not None
        assert env is not None
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="passed\n",
        )
    if tuple(command) == ("git", "apply", "--whitespace=nowarn", "-"):
        assert check is False
        assert cwd is not None
        assert env is None
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="")
    raise AssertionError(f"unexpected subprocess command: {command!r}")
