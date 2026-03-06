"""Git-backed checkpoint helpers for deterministic task rollback."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Final

CHECKPOINT_PREFIX: Final[str] = "[aiw-checkpoint]"
BASELINE_SUFFIX: Final[str] = "baseline"
TASK_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^TASK-\d{3}$")


def create_checkpoint(label: str) -> str:
    """Create a checkpoint commit and return its commit ref."""
    normalized_label = _normalize_label(label)
    _ensure_git_repository()
    _run_git_command("add", "-A")
    _run_git_command(
        "commit",
        "--allow-empty",
        "-m",
        _checkpoint_message(normalized_label),
    )
    return _run_git_command("rev-parse", "HEAD")


def revert_to_checkpoint(ref: str) -> None:
    """Reset the working tree to an existing checkpoint ref."""
    normalized_ref = ref.strip()
    if not normalized_ref:
        raise ValueError("checkpoint ref must be a non-empty string")

    _ensure_git_repository()
    _run_git_command("reset", "--hard", normalized_ref)
    _run_git_command("clean", "-fd")


def get_baseline_ref(task_id: str) -> str:
    """Return the most recent baseline checkpoint ref for a task."""
    normalized_task_id = task_id.strip()
    if not TASK_ID_PATTERN.fullmatch(normalized_task_id):
        raise ValueError(f"invalid task id: {task_id!r}")

    _ensure_git_repository()
    baseline_label = f"{normalized_task_id} {BASELINE_SUFFIX}"
    message = _checkpoint_message(baseline_label)
    return _run_git_command(
        "log",
        "-1",
        "--format=%H",
        f"--grep=^{re.escape(message)}$",
    )


def _ensure_git_repository() -> None:
    _run_git_command("rev-parse", "--show-toplevel")


def _normalize_label(label: str) -> str:
    normalized_label = label.strip()
    if not normalized_label:
        raise ValueError("checkpoint label must be a non-empty string")
    return normalized_label


def _checkpoint_message(label: str) -> str:
    return f"{CHECKPOINT_PREFIX} {label}"


def _run_git_command(*args: str) -> str:
    try:
        completed = subprocess.run(
            ("git", *args),
            check=True,
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        stdout = exc.stdout.strip()
        detail = stderr or stdout
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"git {' '.join(args)} failed{suffix}") from exc

    return completed.stdout.strip()
