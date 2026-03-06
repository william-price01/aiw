"""Tests for spec-phase approve command implementations."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from aiw.cli.init_cmd import init_project
from aiw.cli.spec_cmds import (
    approve_adrs,
    approve_constraints,
    approve_prd,
    approve_sdd,
)
from aiw.orchestrator.spec_phase import SpecApprovalResult
from aiw.workflow import IllegalStateTransitionError


@pytest.mark.parametrize(
    ("command", "start_state", "expected_state", "expected_locked_path"),
    [
        (approve_prd, "PRD_DRAFT", "PRD_APPROVED", "docs/prd.md"),
        (approve_sdd, "SDD_DRAFT", "SDD_APPROVED", "docs/sdd.md"),
        (approve_adrs, "ADRS_DRAFT", "ADRS_APPROVED", "docs/adrs/**"),
        (
            approve_constraints,
            "CONSTRAINTS_DRAFT",
            "CONSTRAINTS_APPROVED",
            "docs/constraints.yml",
        ),
    ],
)
def test_spec_approve_commands_transition_and_lock_artifact(
    tmp_path: Path,
    command: Callable[[Path], SpecApprovalResult],
    start_state: str,
    expected_state: str,
    expected_locked_path: str,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, start_state)

    result = command(repo_root)

    assert isinstance(result, SpecApprovalResult)
    assert result.state == expected_state
    assert result.approved_artifact == expected_locked_path
    assert expected_locked_path in result.locked_paths
    assert _read_workflow_state(repo_root)["state"] == expected_state
    assert _read_workflow_state(repo_root)["current_state"] == expected_state


@pytest.mark.parametrize(
    ("command", "wrong_state"),
    [
        (approve_prd, "INIT"),
        (approve_sdd, "PRD_APPROVED"),
        (approve_adrs, "SDD_APPROVED"),
        (approve_constraints, "ADRS_APPROVED"),
    ],
)
def test_spec_approve_commands_fail_hard_in_wrong_state(
    tmp_path: Path,
    command: Callable[[Path], SpecApprovalResult],
    wrong_state: str,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, wrong_state)

    with pytest.raises(IllegalStateTransitionError):
        command(repo_root)


def _init_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "docs" / "adrs").mkdir(parents=True)
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
