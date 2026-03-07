"""Tests for CLI state validation and stale EXECUTING startup handling."""

from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from typing import Any

import pytest

from aiw.infra import load_constraints

cli_main_module = importlib.import_module("aiw.cli.main")

COMMAND_CASES = [
    ("init", ["init"]),
    ("prd", ["prd"]),
    ("approve-prd", ["approve-prd"]),
    ("sdd", ["sdd"]),
    ("approve-sdd", ["approve-sdd"]),
    ("adrs", ["adrs"]),
    ("approve-adrs", ["approve-adrs"]),
    ("constraints", ["constraints"]),
    ("approve-constraints", ["approve-constraints"]),
    ("decompose", ["decompose"]),
    ("go", ["go", "TASK-001"]),
    ("undo", ["undo"]),
    ("reset", ["reset", "TASK-001"]),
    (
        "request-change",
        [
            "request-change",
            "docs/prd.md",
            "--reason",
            "Clarify acceptance criteria",
            "--impact",
            "Re-approval required",
        ],
    ),
]
CONSTRAINTS = load_constraints(Path("docs/constraints.yml"))
STATES_EXCEPT_EXECUTING = [
    state for state in CONSTRAINTS.workflow.states if state != "EXECUTING"
]


@pytest.mark.parametrize("state", STATES_EXCEPT_EXECUTING)
@pytest.mark.parametrize(("command_name", "argv"), COMMAND_CASES)
def test_cli_state_validation_covers_all_non_stale_state_command_combinations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    state: str,
    command_name: str,
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    repo_root = _init_repo(tmp_path, state=state)
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    _patch_handlers(monkeypatch, calls)
    caplog.set_level(logging.ERROR)

    result = cli_main_module.main(argv, root=repo_root)

    allowed_commands = _allowed_commands_for_state(state)
    canonical_command = _canonical_command(command_name)
    if canonical_command in allowed_commands:
        assert result == 0
        assert len(calls) == 1
        assert capsys.readouterr().err == ""
        assert "state_validation_failed" not in caplog.text
        return

    captured = capsys.readouterr()
    assert result == 1
    assert calls == []
    assert f"state {state!r}" in captured.err
    assert ", ".join(allowed_commands) in captured.err
    assert "state_validation_failed" in caplog.text


@pytest.mark.parametrize(("command_name", "argv"), COMMAND_CASES)
def test_cli_startup_stale_executing_transitions_to_blocked_for_any_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    command_name: str,
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = _init_repo(tmp_path, state="EXECUTING")
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    _patch_handlers(monkeypatch, calls)

    result = cli_main_module.main(argv, root=repo_root)

    captured = capsys.readouterr()
    assert result == 1
    assert calls == []
    assert "stale EXECUTING state detected" in captured.err
    assert _read_state(repo_root)["current_state"] == "BLOCKED"
    assert _read_state(repo_root)["state"] == "BLOCKED"


def test_cli_state_validation_error_message_includes_current_state_and_allowed_commands(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = _init_repo(tmp_path, state="PRD_DRAFT")
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    _patch_handlers(monkeypatch, calls)

    result = cli_main_module.main(["decompose"], root=repo_root)

    captured = capsys.readouterr()
    assert result == 1
    assert calls == []
    assert "state 'PRD_DRAFT'" in captured.err
    assert "edit docs/prd.md, aiw approve-prd" in captured.err


def _allowed_commands_for_state(state: str) -> list[str]:
    return CONSTRAINTS.workflow.allowed_commands_by_state.get(state, [])


def _canonical_command(command_name: str) -> str:
    if command_name == "go":
        return "aiw go TASK-###"
    if command_name == "reset":
        return "aiw reset TASK-###"
    return f"aiw {command_name}"


def _init_repo(tmp_path: Path, *, state: str) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "docs").mkdir(parents=True)
    (repo_root / ".aiw").mkdir(parents=True)
    constraints_text = Path("docs/constraints.yml").read_text(encoding="utf-8")
    (repo_root / "docs" / "constraints.yml").write_text(
        constraints_text,
        encoding="utf-8",
    )
    (repo_root / ".aiw" / "workflow_state.json").write_text(
        json.dumps({"current_state": state, "state": state}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return repo_root


def _patch_handlers(
    monkeypatch: pytest.MonkeyPatch,
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]],
) -> None:
    def recorder(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    for name in (
        "init_project",
        "prd",
        "approve_prd",
        "sdd",
        "approve_sdd",
        "adrs",
        "approve_adrs",
        "constraints",
        "approve_constraints",
        "decompose",
        "go",
        "undo",
        "reset",
        "request_change",
    ):
        monkeypatch.setattr(cli_main_module, name, recorder)


def _read_state(repo_root: Path) -> dict[str, Any]:
    payload = json.loads(
        (repo_root / ".aiw" / "workflow_state.json").read_text(encoding="utf-8")
    )
    if not isinstance(payload, dict):
        raise AssertionError("workflow state payload must be a JSON object")
    return payload
