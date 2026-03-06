"""Tests for git-backed checkpoint creation and rollback."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aiw.infra.checkpoint import (
    create_checkpoint,
    get_baseline_ref,
    revert_to_checkpoint,
)


@pytest.fixture
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    subprocess.run(
        ("git", "init"),
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ("git", "config", "user.name", "AIW Tests"),
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ("git", "config", "user.email", "aiw-tests@example.com"),
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(
        ("git", "add", "README.md"),
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ("git", "commit", "-m", "seed"),
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_create_checkpoint_creates_git_commit_with_deterministic_message(
    git_repo: Path,
) -> None:
    target = git_repo / "feature.txt"
    target.write_text("v1\n", encoding="utf-8")

    ref = create_checkpoint("TASK-011 iteration 1")

    head = _git(git_repo, "rev-parse", "HEAD")
    message = _git(git_repo, "log", "-1", "--format=%s")

    assert ref == head
    assert message == "[aiw-checkpoint] TASK-011 iteration 1"


def test_revert_to_checkpoint_restores_working_tree_exactly(git_repo: Path) -> None:
    tracked = git_repo / "tracked.txt"
    tracked.write_text("before\n", encoding="utf-8")
    checkpoint_ref = create_checkpoint("TASK-011 iteration 1")

    tracked.write_text("after\n", encoding="utf-8")
    (git_repo / "untracked.txt").write_text("temp\n", encoding="utf-8")

    revert_to_checkpoint(checkpoint_ref)

    assert tracked.read_text(encoding="utf-8") == "before\n"
    assert not (git_repo / "untracked.txt").exists()
    assert _git(git_repo, "status", "--short") == ""


def test_get_baseline_ref_returns_latest_baseline_for_task(git_repo: Path) -> None:
    (git_repo / "a.txt").write_text("one\n", encoding="utf-8")
    first_baseline = create_checkpoint("TASK-011 baseline")
    (git_repo / "a.txt").write_text("two\n", encoding="utf-8")
    create_checkpoint("TASK-011 iteration 1")
    (git_repo / "a.txt").write_text("three\n", encoding="utf-8")
    latest_baseline = create_checkpoint("TASK-011 baseline")

    assert get_baseline_ref("TASK-011") == latest_baseline
    assert latest_baseline != first_baseline


def test_get_baseline_ref_rejects_invalid_task_id(git_repo: Path) -> None:
    with pytest.raises(ValueError):
        get_baseline_ref("task-11")


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        check=True,
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
