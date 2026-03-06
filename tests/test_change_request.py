"""Tests for change request file creation and re-approval rollback."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiw.cli.change_request_cmd import request_change
from aiw.cli.init_cmd import init_project
from aiw.infra import load_constraints
from aiw.workflow import IllegalStateTransitionError, WorkflowStateMachine
from aiw.workflow.change_request import (
    ChangeRequest,
    apply_change_request,
    create_change_request,
)


def test_create_change_request_writes_required_fields(tmp_path: Path) -> None:
    output_path = tmp_path / "docs" / "requests" / "CHANGE_REQUEST.md"

    result = create_change_request(
        target="docs/prd.md",
        reason="Need to clarify acceptance criteria",
        impact="PRD must be re-approved before implementation continues",
        output_path=output_path,
    )

    assert result == output_path
    assert output_path.read_text(encoding="utf-8") == (
        "# Change Request\n\n"
        "- target artifact: docs/prd.md\n"
        "- reason: Need to clarify acceptance criteria\n"
        "- impact: PRD must be re-approved before implementation continues\n"
    )


@pytest.mark.parametrize(
    ("target", "start_state", "expected_state"),
    [
        ("docs/prd.md", "PRD_APPROVED", "PRD_DRAFT"),
        ("docs/prd.md", "PLANNED", "PRD_DRAFT"),
        ("docs/prd.md", "BLOCKED", "PRD_DRAFT"),
        ("docs/sdd.md", "SDD_APPROVED", "SDD_DRAFT"),
        ("docs/adrs/ADR-001-example.md", "ADRS_APPROVED", "ADRS_DRAFT"),
        ("docs/constraints.yml", "CONSTRAINTS_APPROVED", "CONSTRAINTS_DRAFT"),
    ],
)
def test_apply_change_request_rolls_back_to_required_draft_state(
    target: str,
    start_state: str,
    expected_state: str,
) -> None:
    config = load_constraints(Path("docs/constraints.yml"))
    machine = WorkflowStateMachine(current_state=start_state)

    apply_change_request(
        request=ChangeRequest(target=target, reason="reason", impact="impact"),
        state_machine=machine,
        config=config,
    )

    assert machine.current_state == expected_state


def test_apply_change_request_rejects_disallowed_workflow_state() -> None:
    config = load_constraints(Path("docs/constraints.yml"))
    machine = WorkflowStateMachine(current_state="INIT")

    with pytest.raises(IllegalStateTransitionError):
        apply_change_request(
            request=ChangeRequest(
                target="docs/prd.md",
                reason="reason",
                impact="impact",
            ),
            state_machine=machine,
            config=config,
        )


@pytest.mark.parametrize(
    ("state", "target", "expected_state"),
    [
        ("PRD_APPROVED", "docs/prd.md", "PRD_DRAFT"),
        ("SDD_APPROVED", "docs/sdd.md", "SDD_DRAFT"),
        ("ADRS_APPROVED", "docs/adrs/ADR-001-example.md", "ADRS_DRAFT"),
        ("CONSTRAINTS_APPROVED", "docs/constraints.yml", "CONSTRAINTS_DRAFT"),
        ("PLANNED", "docs/prd.md", "PRD_DRAFT"),
        ("BLOCKED", "docs/constraints.yml", "CONSTRAINTS_DRAFT"),
    ],
)
def test_request_change_command_creates_file_and_updates_state(
    tmp_path: Path,
    state: str,
    target: str,
    expected_state: str,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, state)

    result = request_change(
        repo_root,
        target=target,
        reason="Need upstream correction",
        impact="Re-approval is required",
    )

    request_path = repo_root / "docs" / "requests" / "CHANGE_REQUEST.md"
    assert result == request_path
    content = request_path.read_text(encoding="utf-8")
    assert f"- target artifact: {target}" in content
    assert "- reason: Need upstream correction" in content
    assert "- impact: Re-approval is required" in content
    assert _read_workflow_state(repo_root)["state"] == expected_state
    assert _read_workflow_state(repo_root)["current_state"] == expected_state


@pytest.mark.parametrize(
    "state",
    ["INIT", "PRD_DRAFT", "SDD_DRAFT", "ADRS_DRAFT", "CONSTRAINTS_DRAFT", "EXECUTING"],
)
def test_request_change_command_fails_in_disallowed_states(
    tmp_path: Path,
    state: str,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, state)

    with pytest.raises(IllegalStateTransitionError):
        request_change(
            repo_root,
            target="docs/prd.md",
            reason="Need upstream correction",
            impact="Re-approval is required",
        )


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
