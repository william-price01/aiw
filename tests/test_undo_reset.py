"""Tests for deterministic undo and reset CLI helpers."""

from __future__ import annotations

import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

import pytest

from aiw.cli.undo_cmd import reset, undo
from aiw.infra.checkpoint import create_checkpoint
from aiw.workflow import IllegalStateTransitionError


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(
        ("git", "init"),
        check=True,
        cwd=repo,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ("git", "config", "user.name", "AIW Tests"),
        check=True,
        cwd=repo,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ("git", "config", "user.email", "aiw-tests@example.com"),
        check=True,
        cwd=repo,
        capture_output=True,
        text=True,
    )

    (repo / ".aiw").mkdir()
    _write_state(repo, "EXECUTING")

    tracked = repo / "tracked.txt"
    tracked.write_text("seed\n", encoding="utf-8")
    subprocess.run(
        ("git", "add", "."),
        check=True,
        cwd=repo,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ("git", "commit", "-m", "seed"),
        check=True,
        cwd=repo,
        capture_output=True,
        text=True,
    )

    return repo


def test_undo_reverts_to_most_recent_checkpoint(repo_root: Path) -> None:
    tracked = repo_root / "tracked.txt"

    with _pushd(repo_root):
        tracked.write_text("baseline\n", encoding="utf-8")
        create_checkpoint("TASK-017 baseline")
        tracked.write_text("iteration-one\n", encoding="utf-8")
        create_checkpoint("TASK-017 iteration 1")
        tracked.write_text("iteration-two\n", encoding="utf-8")
        latest_ref = create_checkpoint("TASK-017 iteration 2")

    tracked.write_text("dirty\n", encoding="utf-8")
    (repo_root / "temp.txt").write_text("remove me\n", encoding="utf-8")

    reverted_ref = undo(repo_root)

    assert reverted_ref == latest_ref
    assert tracked.read_text(encoding="utf-8") == "iteration-two\n"
    assert not (repo_root / "temp.txt").exists()
    assert _git(repo_root, "status", "--short") == ""


def test_reset_reverts_to_task_baseline(repo_root: Path) -> None:
    tracked = repo_root / "tracked.txt"

    with _pushd(repo_root):
        tracked.write_text("baseline\n", encoding="utf-8")
        baseline_ref = create_checkpoint("TASK-017 baseline")
        tracked.write_text("iteration-one\n", encoding="utf-8")
        create_checkpoint("TASK-017 iteration 1")
        tracked.write_text("iteration-two\n", encoding="utf-8")
        create_checkpoint("TASK-017 iteration 2")

    tracked.write_text("dirty\n", encoding="utf-8")

    reverted_ref = reset(repo_root, "TASK-017")

    assert reverted_ref == baseline_ref
    assert tracked.read_text(encoding="utf-8") == "baseline\n"
    assert _git(repo_root, "status", "--short") == ""


@pytest.mark.parametrize("command", [undo, reset])
def test_undo_and_reset_refuse_outside_executing(
    repo_root: Path,
    command: Callable[..., str],
) -> None:
    _write_state(repo_root, "PLANNED")

    with pytest.raises(IllegalStateTransitionError):
        if command is undo:
            undo(repo_root)
        else:
            reset(repo_root, "TASK-017")


def _write_state(repo_root: Path, state: str) -> None:
    state_path = repo_root / ".aiw" / "workflow_state.json"
    state_path.write_text(
        json.dumps({"current_state": state, "state": state}, indent=2) + "\n",
        encoding="utf-8",
    )


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        check=True,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


@contextmanager
def _pushd(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    try:
        os.chdir(path.resolve())
        yield
    finally:
        os.chdir(previous)
