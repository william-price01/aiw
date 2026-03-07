"""CLI helpers for deterministic git-backed undo and reset."""

from __future__ import annotations

import json
import os
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from aiw.infra.checkpoint import (
    CHECKPOINT_PREFIX,
    get_baseline_ref,
    revert_to_checkpoint,
)
from aiw.workflow import IllegalStateTransitionError


def undo(root: Path) -> str:
    """Revert the repository to the most recent checkpoint ref."""
    _ensure_executing_state(root, "aiw undo")
    with _pushd(root):
        checkpoint_ref = _latest_checkpoint_ref()
        revert_to_checkpoint(checkpoint_ref)
    return checkpoint_ref


def reset(root: Path, task_id: str) -> str:
    """Revert the repository to the stored baseline checkpoint for a task."""
    _ensure_executing_state(root, "aiw reset TASK-###")
    with _pushd(root):
        baseline_ref = get_baseline_ref(task_id)
        revert_to_checkpoint(baseline_ref)
    return baseline_ref


def _ensure_executing_state(root: Path, command: str) -> None:
    state_path = root / ".aiw" / "workflow_state.json"
    current_state = _read_current_state(state_path)
    if current_state != "EXECUTING":
        raise IllegalStateTransitionError(
            f"Illegal transition from {current_state!r} with {command!r}"
        )


def _read_current_state(state_path: Path) -> str:
    if not state_path.exists():
        return "INIT"

    data = json.loads(state_path.read_text(encoding="utf-8"))
    for key in ("current_state", "state"):
        value = data.get(key)
        if isinstance(value, str):
            return value

    raise ValueError(
        "workflow state file missing string field 'current_state' or 'state'"
    )


def _latest_checkpoint_ref() -> str:
    message_prefix = re.escape(f"{CHECKPOINT_PREFIX} ")
    return _run_git_command(
        "log",
        "-1",
        "--format=%H",
        f"--grep=^{message_prefix}",
    )


def _run_git_command(*args: str) -> str:
    try:
        completed = subprocess.run(
            ("git", *args),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        stdout = exc.stdout.strip()
        detail = stderr or stdout
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"git {' '.join(args)} failed{suffix}") from exc
    return completed.stdout.strip()


@contextmanager
def _pushd(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    try:
        os.chdir(path.resolve())
        yield
    finally:
        os.chdir(previous)
