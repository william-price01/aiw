"""Tests for decompose AI session context and output validation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from aiw.cli.init_cmd import init_project
from aiw.orchestrator.decompose import (
    DecomposeOutputError,
    PcpPaths,
    invoke_decompose_session,
    run_decompose,
)
from aiw.orchestrator.decompose_validator import validate_decompose_output
from aiw.workflow.gates import GIT_ACCESS_COMMAND


def test_invoke_decompose_session_uses_pcp_content(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    pcp_paths = PcpPaths(
        repo_root,
        {
            "docs/prd.md": repo_root / "docs" / "prd.md",
            "docs/sdd.md": repo_root / "docs" / "sdd.md",
        },
    )
    for path in pcp_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"content for {path.name}\n", encoding="utf-8")

    observed: dict[str, object] = {}

    def fake_runner(
        received_paths: object,
        prompt: str,
    ) -> dict[str, str]:
        observed["paths"] = received_paths
        observed["prompt"] = prompt
        return _valid_output()

    monkeypatch.setattr(
        "aiw.orchestrator.decompose._run_bounded_decompose_ai_session",
        fake_runner,
    )

    output = invoke_decompose_session(pcp_paths)

    assert output == _valid_output()
    assert observed["paths"] is pcp_paths
    prompt = observed["prompt"]
    assert isinstance(prompt, str)
    assert "Generate deterministic planning artifacts for AIW decompose." in prompt
    assert "[docs/prd.md]" in prompt
    assert "content for prd.md" in prompt
    assert "[docs/sdd.md]" in prompt
    assert "content for sdd.md" in prompt


def test_validate_decompose_output_accepts_valid_output() -> None:
    assert validate_decompose_output(_valid_output()) == []


def test_validate_decompose_output_detects_missing_dag_md() -> None:
    output = _valid_output()
    output.pop("DAG.md")

    assert validate_decompose_output(output) == ["Missing DAG.md"]


def test_validate_decompose_output_detects_invalid_dag_yaml() -> None:
    output = _valid_output()
    output["DAG.yml"] = "tasks: [\n"

    errors = validate_decompose_output(output)

    assert len(errors) == 1
    assert errors[0].startswith("Invalid DAG.yml YAML:")


def test_validate_decompose_output_detects_missing_task_files() -> None:
    output = {
        "DAG.md": "# DAG\n",
        "DAG.yml": "tasks: []\n",
    }

    assert validate_decompose_output(output) == ["Missing TASK-###.md files"]


def test_validate_decompose_output_detects_missing_task_fields() -> None:
    output = _valid_output()
    output["TASK-001.md"] = "Type: IMPLEMENTATION\nDepends_on: []\n"

    errors = validate_decompose_output(output)

    assert "TASK-001.md missing required field: Objective" in errors
    assert "TASK-001.md missing required field: File scope allowlist" in errors
    assert "TASK-001.md missing required field: Non-goals" in errors
    assert "TASK-001.md missing required field: Acceptance criteria" in errors
    assert "TASK-001.md missing required field: Tests / checks required" in errors


def test_run_decompose_aborts_before_atomic_write_on_invalid_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    _write_workflow_state(repo_root, "CONSTRAINTS_APPROVED")

    monkeypatch.setattr(
        "aiw.workflow.gates.subprocess.run",
        _successful_git_run,
    )
    monkeypatch.setattr(
        "aiw.orchestrator.decompose.invoke_decompose_session",
        lambda pcp_paths: {
            "DAG.yml": "tasks: []\n",
            "TASK-001.md": "Type: IMPLEMENTATION\n",
        },
    )

    with pytest.raises(DecomposeOutputError, match="Missing DAG.md"):
        run_decompose(repo_root)

    assert not (repo_root / "docs" / "tasks").exists()


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
    adrs_root.mkdir()
    (adrs_root / "ADR-001.md").write_text("# ADR\n", encoding="utf-8")
    return repo_root


def _write_workflow_state(repo_root: Path, state: str) -> None:
    state_path = repo_root / ".aiw" / "workflow_state.json"
    state_path.write_text(
        json.dumps({"state": state}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _valid_output() -> dict[str, str]:
    return {
        "DAG.md": "# DAG\n",
        "DAG.yml": (
            "tasks:\n"
            "  - id: TASK-001\n"
            "    title: Example\n"
            "    type: IMPLEMENTATION\n"
            "    depends_on: []\n"
            "    filescope: [\"aiw/example.py\"]\n"
            "    tests: [\"pytest -q\"]\n"
            "    acceptance: [\"works\"]\n"
        ),
        "TASK-001.md": """## TASK-001: Example

Type: IMPLEMENTATION
Depends_on: []

Objective:
Do something deterministic.

File scope allowlist:
- aiw/example.py

Non-goals:
- No unrelated edits.

Acceptance criteria (measurable):
- Works.

Tests / checks required:
- pytest -q
""",
    }


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
