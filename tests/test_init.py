"""Tests for `aiw init` scaffold creation."""

from __future__ import annotations

import json
from pathlib import Path

from aiw.cli import init_project


def test_init_project_creates_minimum_internal_state_in_git_repo(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()

    init_project(repo_root)

    assert (repo_root / ".aiw").is_dir()
    assert (repo_root / ".aiw" / "runs").is_dir()

    state_file = repo_root / ".aiw" / "workflow_state.json"
    assert state_file.is_file()
    assert json.loads(state_file.read_text(encoding="utf-8")) == {"state": "INIT"}


def test_init_project_is_idempotent_and_does_not_overwrite_existing_state(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()

    init_project(repo_root)

    state_file = repo_root / ".aiw" / "workflow_state.json"
    state_file.write_text(
        json.dumps({"custom": "keep", "state": "PLANNED"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    existing_state = state_file.read_text(encoding="utf-8")

    init_project(repo_root)

    assert state_file.read_text(encoding="utf-8") == existing_state
    assert (repo_root / ".aiw" / "runs").is_dir()
