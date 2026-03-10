"""Tests for the top-level AIW CLI router."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

cli_main_module = importlib.import_module("aiw.cli.main")


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (["init"], "init_project", ()),
        (["prd"], "prd", ()),
        (["approve-prd"], "approve_prd", ()),
        (["sdd"], "sdd", ()),
        (["approve-sdd"], "approve_sdd", ()),
        (["adrs"], "adrs", ()),
        (["approve-adrs"], "approve_adrs", ()),
        (["constraints"], "constraints", ()),
        (["approve-constraints"], "approve_constraints", ()),
        (["decompose"], "decompose", ()),
        (["go", "TASK-021"], "go", ("TASK-021",)),
        (["undo"], "undo", ()),
        (["reset", "TASK-021"], "reset", ("TASK-021",)),
    ],
)
def test_main_routes_each_command_to_the_expected_handler(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    argv: list[str],
    handler_name: str,
    expected: tuple[str, ...],
) -> None:
    calls: list[tuple[Path, tuple[str, ...]]] = []
    return_value = _handler_return_value(handler_name)

    def fake_handler(root: Path, *args: str) -> object:
        calls.append((root, args))
        return return_value

    monkeypatch.setattr(cli_main_module, handler_name, fake_handler)

    result = cli_main_module.main(argv, root=tmp_path)

    assert result == 0
    assert calls == [(tmp_path, expected)]


def test_main_routes_request_change_with_named_arguments(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[Path, str, str, str]] = []

    def fake_request_change(root: Path, target: str, reason: str, impact: str) -> None:
        calls.append((root, target, reason, impact))

    monkeypatch.setattr(cli_main_module, "request_change", fake_request_change)

    result = cli_main_module.main(
        [
            "request-change",
            "docs/prd.md",
            "--reason",
            "Clarify acceptance criteria",
            "--impact",
            "Re-approval required",
        ],
        root=tmp_path,
    )

    assert result == 0
    assert calls == [
        (
            tmp_path,
            "docs/prd.md",
            "Clarify acceptance criteria",
            "Re-approval required",
        )
    ]


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected_stdout"),
    [
        (["init"], "init_project", "ok: initialized .aiw/ [state: INIT]\n"),
        (["prd"], "prd", "ok: entered PRD drafting [state: PRD_DRAFT]\n"),
        (
            ["approve-prd"],
            "approve_prd",
            "ok: PRD approved and locked [state: PRD_APPROVED]\n",
        ),
        (["sdd"], "sdd", "ok: entered SDD drafting [state: SDD_DRAFT]\n"),
        (
            ["approve-sdd"],
            "approve_sdd",
            "ok: SDD approved and locked [state: SDD_APPROVED]\n",
        ),
        (["adrs"], "adrs", "ok: entered ADR drafting [state: ADRS_DRAFT]\n"),
        (
            ["approve-adrs"],
            "approve_adrs",
            "ok: ADRs approved and locked [state: ADRS_APPROVED]\n",
        ),
        (
            ["constraints"],
            "constraints",
            "ok: entered constraints drafting [state: CONSTRAINTS_DRAFT]\n",
        ),
        (
            ["approve-constraints"],
            "approve_constraints",
            "ok: constraints approved and locked [state: CONSTRAINTS_APPROVED]\n",
        ),
        (
            ["decompose"],
            "decompose",
            "ok: decomposed into 2 tasks [state: PLANNED]\n",
        ),
        (
            ["go", "TASK-021"],
            "go",
            "ok: TASK-021 PASS [run_id: run-123]\n",
        ),
        (["undo"], "undo", "ok: reverted to last checkpoint\n"),
        (["reset", "TASK-021"], "reset", "ok: reset to TASK-021 baseline\n"),
    ],
)
def test_main_prints_confirmation_output_for_successful_commands(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    argv: list[str],
    handler_name: str,
    expected_stdout: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_main_module,
        handler_name,
        lambda root, *args: _handler_return_value(handler_name),
    )

    result = cli_main_module.main(argv, root=tmp_path)

    captured = capsys.readouterr()
    assert result == 0
    assert captured.out == expected_stdout
    assert captured.err == ""


def test_main_prints_confirmation_output_for_request_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_main_module,
        "request_change",
        lambda root, target, reason, impact: (
            tmp_path / "docs" / "requests" / "CHANGE_REQUEST.md"
        ),
    )

    result = cli_main_module.main(
        [
            "request-change",
            "docs/prd.md",
            "--reason",
            "Clarify acceptance criteria",
            "--impact",
            "Re-approval required",
        ],
        root=tmp_path,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert (
        captured.out
        == "ok: change request written to docs/requests/CHANGE_REQUEST.md\n"
    )
    assert captured.err == ""


def test_main_prints_blocked_go_result_to_stderr_and_returns_exit_code_1(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_main_module,
        "go",
        lambda root, task_id: SimpleNamespace(status="BLOCKED", run_id="run-999"),
    )

    result = cli_main_module.main(["go", "TASK-021"], root=tmp_path)

    captured = capsys.readouterr()
    assert result == 1
    assert captured.out == ""
    assert captured.err == "blocked: TASK-021 BLOCKED [run_id: run-999]\n"


def test_main_returns_exit_code_1_for_unknown_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = cli_main_module.main(["unknown"])

    captured = capsys.readouterr()
    assert result == 1
    assert "usage: aiw" in captured.out
    assert "invalid choice" in captured.err


@pytest.mark.parametrize(
    ("argv", "expected_text"),
    [
        (["--help"], "request-change"),
        (["go", "--help"], "TASK-021"),
    ],
)
def test_main_exposes_help_text(
    argv: list[str],
    expected_text: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = cli_main_module.main(argv)

    captured = capsys.readouterr()
    assert result == 0
    assert expected_text in captured.out


def test_main_logs_command_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(cli_main_module, "init_project", lambda root: None)
    caplog.set_level(logging.INFO)

    result = cli_main_module.main(["init"], root=tmp_path)

    assert result == 0
    assert "command_dispatch command=init" in caplog.text


def _handler_return_value(handler_name: str) -> object:
    if handler_name == "prd":
        return SimpleNamespace(state="PRD_DRAFT")
    if handler_name == "approve_prd":
        return SimpleNamespace(state="PRD_APPROVED")
    if handler_name == "sdd":
        return SimpleNamespace(state="SDD_DRAFT")
    if handler_name == "approve_sdd":
        return SimpleNamespace(state="SDD_APPROVED")
    if handler_name == "adrs":
        return SimpleNamespace(state="ADRS_DRAFT")
    if handler_name == "approve_adrs":
        return SimpleNamespace(state="ADRS_APPROVED")
    if handler_name == "constraints":
        return SimpleNamespace(state="CONSTRAINTS_DRAFT")
    if handler_name == "approve_constraints":
        return SimpleNamespace(state="CONSTRAINTS_APPROVED")
    if handler_name == "decompose":
        return SimpleNamespace(
            state="PLANNED",
            written_files=(
                "docs/tasks/DAG.md",
                "docs/tasks/DAG.yml",
                "docs/tasks/TASK-001.md",
                "docs/tasks/TASK-002.md",
            ),
        )
    if handler_name == "go":
        return SimpleNamespace(status="PASS", run_id="run-123")
    return None
