"""Change request creation and re-approval state rollback."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from aiw.infra import load_constraints
from aiw.infra.constraints import ConstraintsConfig, ReapprovalTransitionConfig
from aiw.workflow.state_machine import (
    IllegalStateTransitionError,
    WorkflowStateMachine,
)

LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

_ARTIFACT_TO_TRANSITION_KEY: Final[tuple[tuple[str, str], ...]] = (
    ("docs/prd.md", "PRD"),
    ("docs/sdd.md", "SDD"),
    ("docs/adrs/", "ADRS"),
    ("docs/constraints.yml", "CONSTRAINTS"),
)


@dataclass(frozen=True)
class ChangeRequest:
    """Structured change request data."""

    target: str
    reason: str
    impact: str


def create_change_request(
    target: str,
    reason: str,
    impact: str,
    output_path: Path,
) -> Path:
    """Write a change request document with the required fields."""
    request = ChangeRequest(target=target, reason=reason, impact=impact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render_change_request(request), encoding="utf-8")
    return output_path


def apply_change_request(
    request: ChangeRequest,
    state_machine: WorkflowStateMachine,
    config: ConstraintsConfig,
) -> None:
    """Roll the workflow state back to the relevant draft state for the target."""
    transition = _transition_for_target(request.target, config)
    if transition is None:
        return

    current_state = state_machine.current_state
    allowed_states = {
        transition.from_state,
        "PLANNED",
        "BLOCKED",
    }
    if current_state not in allowed_states:
        raise IllegalStateTransitionError(
            f"Illegal transition from {current_state!r} with 'aiw request-change'"
        )

    LOGGER.info(
        "state_transition from=%s action=%s to=%s",
        current_state,
        "aiw request-change",
        transition.to_state,
    )
    state_machine._current_state = transition.to_state


def _render_change_request(request: ChangeRequest) -> str:
    return (
        "# Change Request\n\n"
        f"- target artifact: {request.target}\n"
        f"- reason: {request.reason}\n"
        f"- impact: {request.impact}\n"
    )


def _transition_for_target(
    target: str, config: ConstraintsConfig
) -> ReapprovalTransitionConfig | None:
    key = _transition_key_for_target(target)
    if key is None:
        return None
    return config.boundaries.change_request.requires_reapproval_transition[key]


def _transition_key_for_target(target: str) -> str | None:
    normalized = target.replace("\\", "/")
    for prefix, key in _ARTIFACT_TO_TRANSITION_KEY:
        if normalized == prefix or normalized.startswith(prefix):
            return key
    return None


def request_change_for_repo(
    root: Path,
    target: str,
    reason: str,
    impact: str,
) -> Path:
    """Create the change request file and apply any required state rollback."""
    config = load_constraints(root / "docs" / "constraints.yml")
    state_path = root / config.workflow.state_file
    current_state = WorkflowStateMachine.load(state_path).current_state
    _ensure_request_change_allowed(config, current_state)

    output_path = root / config.boundaries.change_request.file
    create_change_request(
        target=target,
        reason=reason,
        impact=impact,
        output_path=output_path,
    )

    if not config.boundaries.change_request.required_for_modifying_locked_artifacts:
        return output_path

    request = ChangeRequest(target=target, reason=reason, impact=impact)
    machine = WorkflowStateMachine(current_state=current_state)
    apply_change_request(request=request, state_machine=machine, config=config)
    machine.save(state_path)
    return output_path


def _ensure_request_change_allowed(
    config: ConstraintsConfig, current_state: str
) -> None:
    allowed_commands = config.workflow.allowed_commands_by_state.get(current_state, [])
    if "aiw request-change" not in allowed_commands:
        raise IllegalStateTransitionError(
            f"Illegal transition from {current_state!r} with 'aiw request-change'"
        )
