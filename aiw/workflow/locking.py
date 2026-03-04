"""Artifact locking rules and lock violation detection."""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path
from typing import Final

from aiw.infra import ConstraintsConfig, load_constraints
from aiw.workflow.state_machine import WORKFLOW_STATES

CONSTRAINTS_PATH: Final[Path] = Path("docs/constraints.yml")
GIT_DIFF_NAME_ONLY_COMMAND: Final[tuple[str, str, str]] = (
    "git",
    "diff",
    "--name-only",
)
STATE_INDEX: Final[dict[str, int]] = {
    state: index for index, state in enumerate(WORKFLOW_STATES)
}


class LockViolationError(RuntimeError):
    """Raised when changes include one or more locked artifacts."""

    violations: tuple[str, ...]

    def __init__(self, violations: list[str]) -> None:
        self.violations = tuple(violations)
        message = ", ".join(violations)
        super().__init__(f"Locked artifact modification detected: {message}")


def get_locked_paths(state: str) -> set[str]:
    """Return lock patterns active for a given workflow state."""
    _validate_state(state)
    config = _load_constraints()

    locked_paths = set(config.boundaries.locked_artifacts.always_locked)
    for lock_rule in config.boundaries.locked_artifacts.lock_after_state:
        _validate_state(lock_rule.state)
        if _is_state_at_or_after(state, lock_rule.state):
            locked_paths.add(lock_rule.artifact)

    if state == "EXECUTING":
        locked_paths.update(config.boundaries.locked_artifacts.immutable_during_execution)

    return locked_paths


def check_lock_violations(state: str, changed_files: list[str]) -> list[str]:
    """Return changed paths that violate lock rules for the given state."""
    _validate_state(state)
    locked_patterns = get_locked_paths(state)

    violations = {
        _normalize_path(changed_path)
        for changed_path in changed_files
        if _is_locked_path(_normalize_path(changed_path), locked_patterns)
    }

    return sorted(path for path in violations if path)


def get_changed_files_via_git_diff_name_only() -> list[str]:
    """Return changed files from `git diff --name-only`."""
    config = _load_constraints()
    if not config.locking_rules.locked_artifacts_checked_via_git_diff_name_only:
        raise RuntimeError(
            "constraints forbid lock checks without git diff --name-only detection"
        )

    try:
        completed = subprocess.run(
            GIT_DIFF_NAME_ONLY_COMMAND,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        detail = f": {stderr}" if stderr else ""
        raise RuntimeError(f"git diff --name-only failed{detail}") from exc

    return [
        _normalize_path(line)
        for line in completed.stdout.splitlines()
        if _normalize_path(line)
    ]


def enforce_lock_rules(state: str, changed_files: list[str] | None = None) -> list[str]:
    """Compute lock violations and raise hard-fail errors when configured."""
    config = _load_constraints()
    files_to_check = changed_files
    if files_to_check is None:
        files_to_check = get_changed_files_via_git_diff_name_only()

    violations = check_lock_violations(state, files_to_check)
    if not violations:
        return violations

    if not config.locking_rules.forbid_silent_edits_to_locked_artifacts:
        return violations

    if state != "EXECUTING":
        raise LockViolationError(violations)
    if config.locking_rules.hard_fail_on_locked_artifact_modification_during_executing:
        raise LockViolationError(violations)
    return violations


def _load_constraints() -> ConstraintsConfig:
    if not CONSTRAINTS_PATH.exists():
        raise FileNotFoundError(f"Missing constraints file: {CONSTRAINTS_PATH}")
    return load_constraints(CONSTRAINTS_PATH)


def _validate_state(state: str) -> None:
    if state not in STATE_INDEX:
        raise ValueError(f"Unknown workflow state: {state}")


def _is_state_at_or_after(state: str, threshold_state: str) -> bool:
    return STATE_INDEX[state] >= STATE_INDEX[threshold_state]


def _normalize_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def _is_locked_path(path: str, locked_patterns: set[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in locked_patterns)
