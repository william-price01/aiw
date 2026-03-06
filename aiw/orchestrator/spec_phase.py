"""Spec-phase draft session orchestration."""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from aiw.infra import ConstraintsConfig, load_constraints
from aiw.workflow import IllegalStateTransitionError, WorkflowStateMachine

COMMAND_TO_ARTIFACT_SCOPE: Final[dict[str, str]] = {
    "aiw prd": "docs/prd.md",
    "aiw sdd": "docs/sdd.md",
    "aiw adrs": "docs/adrs/**",
    "aiw constraints": "docs/constraints.yml",
}


class DraftScopeViolationError(RuntimeError):
    """Raised when an edit falls outside the active draft artifact scope."""


@dataclass(frozen=True)
class SpecDraftSession:
    """Active spec drafting session metadata and scope enforcement."""

    root: Path
    state: str
    command: str
    active_artifact_scope: str

    def allows_path(self, path: str | Path) -> bool:
        """Return whether a path is editable in this draft session."""
        normalized = _normalize_relpath(self.root, path)
        return fnmatch.fnmatchcase(normalized, self.active_artifact_scope)

    def assert_path_allowed(self, path: str | Path) -> Path:
        """Return the absolute path when the edit target is in scope."""
        if not self.allows_path(path):
            normalized = _normalize_relpath(self.root, path)
            raise DraftScopeViolationError(
                f"{normalized!r} is outside active draft scope "
                f"{self.active_artifact_scope!r}"
            )
        return self.root / _normalize_relpath(self.root, path)


def enter_spec_draft(root: Path, command: str) -> SpecDraftSession:
    """Transition into a spec-phase DRAFT state and return the active scope."""
    constraints_path = root / "docs" / "constraints.yml"
    config = load_constraints(constraints_path)
    state_path = root / config.workflow.state_file
    current_state = _read_current_state(state_path)
    _ensure_command_allowed(config, current_state, command)

    machine = WorkflowStateMachine(current_state=current_state)
    next_state = machine.transition(command)
    _write_current_state(state_path, next_state)

    return SpecDraftSession(
        root=root,
        state=next_state,
        command=command,
        active_artifact_scope=_artifact_scope_for_command(command),
    )


def _artifact_scope_for_command(command: str) -> str:
    try:
        return COMMAND_TO_ARTIFACT_SCOPE[command]
    except KeyError as exc:
        raise ValueError(f"Unsupported spec draft command: {command}") from exc


def _ensure_command_allowed(
    config: ConstraintsConfig, current_state: str, command: str
) -> None:
    allowed_commands = config.workflow.allowed_commands_by_state.get(current_state, [])
    if command not in allowed_commands:
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


def _write_current_state(state_path: Path, state: str) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"current_state": state, "state": state}
    state_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _normalize_relpath(root: Path, path: str | Path) -> str:
    path_obj = Path(path)
    if path_obj.is_absolute():
        path_obj = path_obj.relative_to(root)
    return path_obj.as_posix()
