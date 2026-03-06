"""Tests for spec-phase draft command implementations."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from aiw.cli.init_cmd import init_project
from aiw.cli.spec_cmds import adrs, constraints, prd, sdd
from aiw.orchestrator import DraftScopeViolationError, SpecDraftSession
from aiw.workflow import IllegalStateTransitionError


@pytest.mark.parametrize(
    ("command", "start_state", "expected_state", "expected_scope"),
    [
        (prd, "INIT", "PRD_DRAFT", "docs/prd.md"),
        (sdd, "PRD_APPROVED", "SDD_DRAFT", "docs/sdd.md"),
        (adrs, "SDD_APPROVED", "ADRS_DRAFT", "docs/adrs/**"),
        (constraints, "ADRS_APPROVED", "CONSTRAINTS_DRAFT", "docs/constraints.yml"),
    ],
)
def test_spec_draft_command_transitions_and_sets_active_scope(
    tmp_path: Path,
    command: Callable[[Path], SpecDraftSession],
    start_state: str,
    expected_state: str,
    expected_scope: str,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, start_state)

    session = command(repo_root)

    assert isinstance(session, SpecDraftSession)
    assert session.state == expected_state
    assert session.active_artifact_scope == expected_scope
    assert _read_workflow_state(repo_root)["state"] == expected_state
    assert _read_workflow_state(repo_root)["current_state"] == expected_state


@pytest.mark.parametrize(
    ("command", "wrong_state"),
    [
        (prd, "PRD_APPROVED"),
        (sdd, "INIT"),
        (adrs, "PRD_APPROVED"),
        (constraints, "SDD_APPROVED"),
    ],
)
def test_spec_draft_commands_fail_hard_in_wrong_state(
    tmp_path: Path,
    command: Callable[[Path], SpecDraftSession],
    wrong_state: str,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, wrong_state)

    with pytest.raises(IllegalStateTransitionError):
        command(repo_root)


@pytest.mark.parametrize(
    ("command", "start_state", "allowed_path", "blocked_path"),
    [
        (prd, "INIT", "docs/prd.md", "docs/sdd.md"),
        (sdd, "PRD_APPROVED", "docs/sdd.md", "docs/prd.md"),
        (adrs, "SDD_APPROVED", "docs/adrs/ADR-001-example.md", "docs/constraints.yml"),
        (
            constraints,
            "ADRS_APPROVED",
            "docs/constraints.yml",
            "docs/adrs/ADR-001-example.md",
        ),
    ],
)
def test_spec_draft_scope_allows_only_active_artifact(
    tmp_path: Path,
    command: Callable[[Path], SpecDraftSession],
    start_state: str,
    allowed_path: str,
    blocked_path: str,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, start_state)

    session = command(repo_root)

    assert session.allows_path(allowed_path) is True
    assert session.assert_path_allowed(allowed_path) == repo_root / allowed_path
    assert session.allows_path(blocked_path) is False
    with pytest.raises(DraftScopeViolationError):
        session.assert_path_allowed(blocked_path)


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
