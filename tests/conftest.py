"""Shared pytest fixtures for AIW tests."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from aiw.cli.init_cmd import init_project
from aiw.orchestrator.coder import DiffStats, PatchResult
from aiw.workflow.gates import GIT_ACCESS_COMMAND


@dataclass
class HappyPathRepo:
    """Isolated repository plus captured side effects for integration tests."""

    root: Path
    checkpoint_calls: list[str]


@pytest.fixture
def happy_path_repo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> HappyPathRepo:
    """Create an isolated repo and stub external execution for happy-path tests."""
    repo_root = tmp_path / "repo"
    (repo_root / ".git").mkdir(parents=True)
    (repo_root / "docs" / "adrs").mkdir(parents=True)
    init_project(repo_root)

    (repo_root / "docs" / "constraints.yml").write_text(
        Path("docs/constraints.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (repo_root / "docs" / "prd.md").write_text(
        "# PRD\n\nHappy-path integration test fixture.\n",
        encoding="utf-8",
    )
    (repo_root / "docs" / "sdd.md").write_text(
        "# SDD\n\nHappy-path integration test fixture.\n",
        encoding="utf-8",
    )
    (repo_root / "docs" / "adrs" / "ADR-001-test.md").write_text(
        "# ADR-001\n\nHappy-path integration test fixture.\n",
        encoding="utf-8",
    )

    checkpoint_calls: list[str] = []

    monkeypatch.setattr(
        "aiw.workflow.gates.subprocess.run",
        _successful_git_gate_run,
    )
    monkeypatch.setattr(
        "aiw.orchestrator.executor.subprocess.run",
        _successful_executor_run,
    )

    def fake_create_checkpoint(label: str) -> str:
        checkpoint_calls.append(label)
        return "checkpoint-ref-123"

    monkeypatch.setattr(
        "aiw.orchestrator.executor.create_checkpoint",
        fake_create_checkpoint,
    )
    monkeypatch.setattr(
        "aiw.orchestrator.executor.run_coder_session",
        _fake_run_coder_session,
    )
    monkeypatch.setattr(
        "aiw.orchestrator.decompose.invoke_decompose_session",
        lambda _pcp_paths: _valid_decompose_output(),
    )

    return HappyPathRepo(root=repo_root, checkpoint_calls=checkpoint_calls)


def _fake_run_coder_session(
    task_spec: object,
    constraints: object,
    repo_root: Path | None = None,
    codex_runner: object | None = None,
) -> PatchResult:
    del task_spec, constraints, repo_root, codex_runner
    return PatchResult(
        changed_files=("tests/integration/test_happy_path.py",),
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
) -> subprocess.CompletedProcess[str]:
    assert tuple(command) == GIT_ACCESS_COMMAND
    assert check is True
    assert capture_output is True
    assert text is True
    return subprocess.CompletedProcess(
        args=command,
        returncode=0,
        stdout="/tmp/repo\n",
    )


def _successful_executor_run(
    command: list[str] | tuple[str, ...],
    *,
    check: bool,
    capture_output: bool,
    text: bool,
    cwd: Path | None = None,
    input: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    assert capture_output is True
    assert text is True
    if tuple(command) == GIT_ACCESS_COMMAND:
        assert check is True
        assert cwd is None
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
        assert input == ""
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="")
    raise AssertionError(f"unexpected subprocess command: {command!r}")


def _valid_decompose_output() -> dict[str, str]:
    return {
        "DAG.md": "# DAG\n",
        "DAG.yml": (
            "tasks:\n"
            "  - id: TASK-001\n"
            "    title: Integration happy path fixture\n"
            "    type: IMPLEMENTATION\n"
            "    depends_on: []\n"
            "    filescope:\n"
            "      - tests/integration/test_happy_path.py\n"
            "    tests:\n"
            "      - pytest -q\n"
            "    acceptance:\n"
            "      - Workflow completes.\n"
        ),
        "TASK-001.md": (
            "## TASK-001: Integration happy path fixture\n\n"
            "Type: IMPLEMENTATION\n"
            "Depends_on: []\n\n"
            "Objective:\n"
            "Exercise the happy path integration test.\n\n"
            "File scope allowlist:\n"
            "- tests/integration/test_happy_path.py\n\n"
            "Non-goals:\n"
            "- No unrelated edits.\n\n"
            "Acceptance criteria (measurable):\n"
            "- Workflow completes.\n\n"
            "Tests / checks required:\n"
            "- pytest -q\n"
        ),
    }
