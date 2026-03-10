"""Tests for decompose command orchestration."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import pytest

from aiw.cli.decompose_cmd import decompose
from aiw.cli.init_cmd import init_project
from aiw.orchestrator.decompose import DecomposeOutputError, DecomposeResult
from aiw.workflow import IllegalStateTransitionError, WorkflowStateMachine
from aiw.workflow.gates import GIT_ACCESS_COMMAND


def test_decompose_refuses_unless_constraints_approved(tmp_path: Path) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, "ADRS_APPROVED")

    with pytest.raises(IllegalStateTransitionError):
        decompose(repo_root)

    assert not (repo_root / "docs" / "tasks").exists()
    assert _read_workflow_state(repo_root) == {"current_state": "ADRS_APPROVED"}


def test_decompose_runs_constraints_gate_before_generation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, "CONSTRAINTS_APPROVED")
    gate_calls: list[str] = []
    session_calls: list[str] = []

    monkeypatch.setattr(
        "aiw.workflow.gates.subprocess.run",
        _successful_git_run,
    )

    def fake_gate(config: object) -> None:
        gate_calls.append("gate")

    def fake_session(root: Path) -> dict[str, str]:
        assert gate_calls == ["gate"]
        session_calls.append(root.as_posix())
        return _valid_output()

    monkeypatch.setattr("aiw.orchestrator.decompose.check_constraints_gate", fake_gate)
    monkeypatch.setattr(
        "aiw.orchestrator.decompose.invoke_decompose_session",
        fake_session,
    )

    result = decompose(repo_root)

    assert isinstance(result, DecomposeResult)
    assert gate_calls == ["gate"]
    assert session_calls == [repo_root.as_posix()]


def test_decompose_ai_failure_leaves_no_partial_task_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, "CONSTRAINTS_APPROVED")
    tasks_dir = repo_root / "docs" / "tasks"

    monkeypatch.setattr(
        "aiw.workflow.gates.subprocess.run",
        _successful_git_run,
    )
    monkeypatch.setattr(
        "aiw.orchestrator.decompose.invoke_decompose_session",
        _failing_session,
    )

    with pytest.raises(RuntimeError, match="session failed"):
        decompose(repo_root)

    assert not tasks_dir.exists()
    assert not list((repo_root / "docs").glob("decompose-*"))
    assert _read_workflow_state(repo_root) == {"current_state": "CONSTRAINTS_APPROVED"}


def test_decompose_writes_outputs_atomically_and_transitions_to_planned(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, "CONSTRAINTS_APPROVED")
    replaced_paths: list[str] = []

    monkeypatch.setattr(
        "aiw.workflow.gates.subprocess.run",
        _successful_git_run,
    )
    monkeypatch.setattr(
        "aiw.orchestrator.decompose.invoke_decompose_session",
        lambda root: _valid_output(),
    )

    original_replace = Path.replace

    def tracking_replace(self: Path, target: Path) -> Path:
        replaced_paths.append(f"{self.name}->{target.name}")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", tracking_replace)
    caplog.set_level(logging.INFO)

    result = decompose(repo_root)

    assert result.state == "PLANNED"
    assert result.written_files == (
        "docs/tasks/DAG.md",
        "docs/tasks/DAG.yml",
        "docs/tasks/TASK-001.md",
    )
    assert (repo_root / "docs" / "tasks" / "DAG.md").read_text(encoding="utf-8") == (
        "# DAG\n"
    )
    assert (repo_root / "docs" / "tasks" / "DAG.yml").read_text(
        encoding="utf-8"
    ) == "tasks: []\n"
    assert (repo_root / "docs" / "tasks" / "TASK-001.md").read_text(
        encoding="utf-8"
    ) == "Task body\n"
    assert any(entry.endswith("->tasks") for entry in replaced_paths)
    assert not list((repo_root / "docs").glob("decompose-*"))
    assert _read_workflow_state(repo_root) == {"current_state": "PLANNED"}
    assert WorkflowStateMachine.load(_state_file(repo_root)).current_state == "PLANNED"
    assert (
        "state_transition from=CONSTRAINTS_APPROVED "
        "action=aiw decompose to=PLANNED"
    ) in caplog.text


def test_decompose_codex_non_zero_exit_raises_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, "CONSTRAINTS_APPROVED")

    monkeypatch.setattr(
        "aiw.workflow.gates._validate_git_repo_access",
        lambda: None,
    )

    def fake_codex_run(
        command: tuple[str, ...],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        assert command[0:2] == ("codex", "exec")
        assert check is True
        assert capture_output is True
        assert text is True
        assert cwd == repo_root
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=command,
            stderr="planner exploded",
        )

    monkeypatch.setattr("aiw.orchestrator.decompose.subprocess.run", fake_codex_run)

    with pytest.raises(DecomposeOutputError, match="planner exploded"):
        decompose(repo_root)

    assert not (repo_root / "docs" / "tasks").exists()
    assert _read_workflow_state(repo_root) == {"current_state": "CONSTRAINTS_APPROVED"}


def test_decompose_missing_codex_cli_raises_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, "CONSTRAINTS_APPROVED")

    monkeypatch.setattr(
        "aiw.workflow.gates._validate_git_repo_access",
        lambda: None,
    )

    def missing_codex_run(
        command: tuple[str, ...],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        assert command[0:2] == ("codex", "exec")
        assert cwd == repo_root
        raise FileNotFoundError("codex")

    monkeypatch.setattr(
        "aiw.orchestrator.decompose.subprocess.run",
        missing_codex_run,
    )

    with pytest.raises(DecomposeOutputError, match="Codex CLI not found"):
        decompose(repo_root)

    assert not (repo_root / "docs" / "tasks").exists()
    assert _read_workflow_state(repo_root) == {"current_state": "CONSTRAINTS_APPROVED"}


def test_decompose_invalid_json_raises_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, "CONSTRAINTS_APPROVED")

    monkeypatch.setattr(
        "aiw.workflow.gates._validate_git_repo_access",
        lambda: None,
    )

    def invalid_json_codex_run(
        command: tuple[str, ...],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        assert command[0:2] == ("codex", "exec")
        assert cwd == repo_root
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="not-json",
        )

    monkeypatch.setattr(
        "aiw.orchestrator.decompose.subprocess.run",
        invalid_json_codex_run,
    )

    with pytest.raises(DecomposeOutputError, match="invalid JSON"):
        decompose(repo_root)

    assert not (repo_root / "docs" / "tasks").exists()
    assert _read_workflow_state(repo_root) == {"current_state": "CONSTRAINTS_APPROVED"}


def _init_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    init_project(repo_root)
    docs_root = repo_root / "docs"
    docs_root.mkdir(exist_ok=True)
    (docs_root / "constraints.yml").write_text(
        Path("docs/constraints.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (docs_root / "prd.md").write_text("# PRD\n", encoding="utf-8")
    (docs_root / "sdd.md").write_text("# SDD\n", encoding="utf-8")
    adrs_root = docs_root / "adrs"
    adrs_root.mkdir(exist_ok=True)
    (adrs_root / "ADR-001.md").write_text("# ADR\n", encoding="utf-8")
    return repo_root


def _write_workflow_state(repo_root: Path, state: str) -> None:
    WorkflowStateMachine(current_state=state).save(_state_file(repo_root))


def _read_workflow_state(repo_root: Path) -> dict[str, str]:
    data = json.loads(_state_file(repo_root).read_text(encoding="utf-8"))
    return {key: str(value) for key, value in data.items()}


def _state_file(repo_root: Path) -> Path:
    return repo_root / ".aiw" / "workflow_state.json"


def _valid_output() -> dict[str, str]:
    return {
        "DAG.md": "# DAG\n",
        "DAG.yml": "tasks: []\n",
        "TASK-001.md": "Task body\n",
    }


def _failing_session(root: Path) -> dict[str, str]:
    raise RuntimeError("session failed")


def _successful_git_run(
    command: tuple[str, ...],
    *,
    check: bool,
    capture_output: bool,
    text: bool,
) -> subprocess.CompletedProcess[str]:
    assert command == GIT_ACCESS_COMMAND
    assert check is True
    assert capture_output is True
    assert text is True
    return subprocess.CompletedProcess(
        args=command,
        returncode=0,
        stdout="/tmp/repo\n",
    )
