"""AIW workflow layer — state machine, locking, and gates."""

from .state_machine import (
    TRANSITIONS,
    WORKFLOW_STATES,
    IllegalStateTransitionError,
    WorkflowStateMachine,
)

__all__ = [
    "IllegalStateTransitionError",
    "TRANSITIONS",
    "WORKFLOW_STATES",
    "WorkflowStateMachine",
]
