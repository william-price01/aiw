"""Tests for workflow preflight gates."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aiw.infra import load_constraints
from aiw.workflow.gates import (
    GIT_ACCESS_COMMAND,
    ConstraintsGateError,
    check_constraints_gate,
)


def test_check_constraints_gate_accepts_valid_constraints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = load_constraints(Path("docs/constraints.yml"))

    monkeypatch.setattr("aiw.workflow.gates.subprocess.run", _successful_git_run)

    check_constraints_gate(config)


def test_check_constraints_gate_rejects_missing_quality_test_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = load_constraints(
        _write_constraints(tmp_path, _replace_test_command_line(""))
    )
    monkeypatch.setattr("aiw.workflow.gates.subprocess.run", _successful_git_run)

    with pytest.raises(ConstraintsGateError) as exc_info:
        check_constraints_gate(config)

    assert exc_info.value.errors == ("Missing required field: quality.test_command",)
    assert exc_info.value.event.event_type == "constraint_validation_failed"
    assert exc_info.value.event.payload == {
        "errors": ["Missing required field: quality.test_command"],
        "refuse_commands": ["aiw decompose", "aiw go TASK-###"],
    }


def test_check_constraints_gate_rejects_tbd_quality_test_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = load_constraints(
        _write_constraints(
            tmp_path,
            _replace_test_command_line('  test_command: "TBD"'),
        )
    )
    monkeypatch.setattr("aiw.workflow.gates.subprocess.run", _successful_git_run)

    with pytest.raises(ConstraintsGateError) as exc_info:
        check_constraints_gate(config)

    assert exc_info.value.errors == (
        "Field quality.test_command contains placeholder value: 'TBD'",
    )


def test_check_constraints_gate_rejects_empty_quality_test_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = load_constraints(
        _write_constraints(
            tmp_path,
            _replace_test_command_line('  test_command: ""'),
        )
    )
    monkeypatch.setattr("aiw.workflow.gates.subprocess.run", _successful_git_run)

    with pytest.raises(ConstraintsGateError) as exc_info:
        check_constraints_gate(config)

    assert exc_info.value.errors == (
        "Field quality.test_command contains placeholder value: ''",
    )


def test_check_constraints_gate_rejects_inaccessible_git_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = load_constraints(Path("docs/constraints.yml"))

    def fake_run(
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
        raise subprocess.CalledProcessError(
            returncode=128,
            cmd=command,
            stderr="fatal: not a git repository",
        )

    monkeypatch.setattr("aiw.workflow.gates.subprocess.run", fake_run)

    with pytest.raises(ConstraintsGateError) as exc_info:
        check_constraints_gate(config)

    assert exc_info.value.errors == (
        "Git repository is not accessible: fatal: not a git repository",
    )
    assert exc_info.value.event.event_type == "constraint_validation_failed"


def _constraints_text() -> str:
    return Path("docs/constraints.yml").read_text(encoding="utf-8")


def _replace_test_command_line(replacement: str) -> str:
    needle = "  test_command: `pytest -q`"
    content = _constraints_text()
    if needle not in content:
        raise AssertionError("expected baseline test_command line in constraints file")
    return content.replace(needle, replacement, 1)


def _write_constraints(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "constraints.yml"
    path.write_text(content, encoding="utf-8")
    return path


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
