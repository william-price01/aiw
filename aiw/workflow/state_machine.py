"""Core workflow state machine for AIW."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Final

LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

WORKFLOW_STATES: Final[tuple[str, ...]] = (
    "INIT",
    "PRD_DRAFT",
    "PRD_APPROVED",
    "SDD_DRAFT",
    "SDD_APPROVED",
    "ADRS_DRAFT",
    "ADRS_APPROVED",
    "CONSTRAINTS_DRAFT",
    "CONSTRAINTS_APPROVED",
    "PLANNED",
    "EXECUTING",
    "BLOCKED",
)

TRANSITIONS: Final[dict[tuple[str, str], str]] = {
    ("INIT", "aiw prd"): "PRD_DRAFT",
    ("PRD_DRAFT", "aiw approve-prd"): "PRD_APPROVED",
    ("PRD_APPROVED", "aiw sdd"): "SDD_DRAFT",
    ("SDD_DRAFT", "aiw approve-sdd"): "SDD_APPROVED",
    ("SDD_APPROVED", "aiw adrs"): "ADRS_DRAFT",
    ("ADRS_DRAFT", "aiw approve-adrs"): "ADRS_APPROVED",
    ("ADRS_APPROVED", "aiw constraints"): "CONSTRAINTS_DRAFT",
    ("CONSTRAINTS_DRAFT", "aiw approve-constraints"): "CONSTRAINTS_APPROVED",
    ("CONSTRAINTS_APPROVED", "aiw decompose"): "PLANNED",
    ("PLANNED", "aiw go TASK-###"): "EXECUTING",
    ("EXECUTING", "on:success"): "PLANNED",
    ("EXECUTING", "on:exhaustion"): "BLOCKED",
    ("EXECUTING", "on:scope_violation_second"): "BLOCKED",
    ("EXECUTING", "on:oversized_split"): "BLOCKED",
    ("EXECUTING", "on:abort"): "PLANNED",
    ("EXECUTING", "on:stale_execution_detected"): "BLOCKED",
}


class IllegalStateTransitionError(RuntimeError):
    """Raised when a requested transition is not valid for the current state."""


class WorkflowStateMachine:
    """Finite state machine for the global AIW workflow."""

    def __init__(
        self,
        current_state: str = "INIT",
        metadata: dict[str, object] | None = None,
    ) -> None:
        if current_state not in WORKFLOW_STATES:
            raise ValueError(f"Unknown workflow state: {current_state}")
        self._current_state = current_state
        self._metadata: dict[str, object] = dict(metadata) if metadata else {}

    @property
    def current_state(self) -> str:
        """Return current workflow state."""
        return self._current_state

    def set_metadata(self, key: str, value: object) -> None:
        """Set a metadata key on the state machine."""
        self._metadata[key] = value

    def get_metadata(self, key: str, default: object = None) -> object:
        """Retrieve a metadata value by key."""
        return self._metadata.get(key, default)

    def transition(self, command: str) -> str:
        """Apply a transition by command/event, returning the resulting state."""
        key = (self._current_state, command)
        next_state = TRANSITIONS.get(key)
        if next_state is None:
            raise IllegalStateTransitionError(
                f"Illegal transition from {self._current_state!r} with {command!r}"
            )

        LOGGER.info(
            "state_transition from=%s action=%s to=%s",
            self._current_state,
            command,
            next_state,
        )
        self._current_state = next_state
        return next_state

    @classmethod
    def load(cls, path: Path) -> WorkflowStateMachine:
        """Load persisted workflow state from JSON; defaults to INIT if absent."""
        if not path.exists():
            return cls()

        data = json.loads(path.read_text(encoding="utf-8"))
        current_state = data.get("current_state")
        if not isinstance(current_state, str):
            raise ValueError("workflow state file missing string field 'current_state'")
        raw_metadata = data.get("metadata")
        metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
        return cls(current_state=current_state, metadata=metadata)

    def save(self, path: Path) -> None:
        """Persist current workflow state to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {"current_state": self._current_state}
        if self._metadata:
            payload["metadata"] = dict(self._metadata)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
