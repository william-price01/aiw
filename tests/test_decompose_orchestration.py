"""Tests for decompose command orchestration."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import pytest

from aiw.cli.decompose_cmd import decompose
from aiw.cli.init_cmd import init_project
from aiw.orchestrator.decompose import DecomposeResult
from aiw.workflow import IllegalStateTransitionError
from aiw.workflow.gates import GIT_ACCESS_COMMAND


def test_decompose_refuses_unless_constraints_approved(tmp_path: Path) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, "ADRS_APPROVED")

    with pytest.raises(IllegalStateTransitionError):
        decompose(repo_root)

    assert not (repo_root / "docs" / "tasks").exists()
    assert _read_workflow_state(repo_root)["state"] == "ADRS_APPROVED"


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
    assert _read_workflow_state(repo_root)["state"] == "CONSTRAINTS_APPROVED"


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
    assert _read_workflow_state(repo_root)["state"] == "PLANNED"
    assert _read_workflow_state(repo_root)["current_state"] == "PLANNED"
    assert (
        "state_transition from=CONSTRAINTS_APPROVED "
        "action=aiw decompose to=PLANNED"
    ) in caplog.text


def _init_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "docs").mkdir()
    init_project(repo_root)
    (repo_root / "docs" / "constraints.yml").write_text(
        Path("docs/constraints.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return repo_root


def _write_workflow_state(repo_root: Path, state: str) -> None:
    state_path = repo_root / ".aiw" / "workflow_state.json"
    state_path.write_text(
        json.dumps({"state": state}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_workflow_state(repo_root: Path) -> dict[str, str]:
    state_path = repo_root / ".aiw" / "workflow_state.json"
    data = json.loads(state_path.read_text(encoding="utf-8"))
    return {key: str(value) for key, value in data.items()}


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
