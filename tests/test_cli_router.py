"""Tests for the top-level AIW CLI router."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

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

    def fake_handler(root: Path, *args: str) -> None:
        calls.append((root, args))

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
