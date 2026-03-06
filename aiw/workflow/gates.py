"""Preflight workflow gates for command execution."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Final

from aiw.infra import ConstraintsConfig, validate_constraints

GIT_ACCESS_COMMAND: Final[tuple[str, str, str]] = (
    "git",
    "rev-parse",
    "--show-toplevel",
)


@dataclass(frozen=True)
class ConstraintValidationFailedEvent:
    """Structured trace event payload for constraint gate failures."""

    event_type: str
    payload: dict[str, object]


class ConstraintsGateError(RuntimeError):
    """Raised when the constraints finalization gate refuses execution."""

    errors: tuple[str, ...]
    event: ConstraintValidationFailedEvent

    def __init__(self, errors: list[str], refused_commands: list[str]) -> None:
        self.errors = tuple(errors)
        self.event = ConstraintValidationFailedEvent(
            event_type="constraint_validation_failed",
            payload={
                "errors": list(self.errors),
                "refuse_commands": list(refused_commands),
            },
        )
        super().__init__(
            "Constraints finalization gate failed: " + "; ".join(self.errors)
        )


def check_constraints_gate(config: ConstraintsConfig) -> None:
    """Validate preflight constraints before allowing execution commands."""
    gate = config.execution.constraints_finalization_gate
    if not gate.enabled:
        return

    errors = validate_constraints(config)
    git_error = _validate_git_repo_access()
    if git_error is not None:
        errors.append(git_error)

    if errors:
        raise ConstraintsGateError(errors, gate.refuse_commands)


def _validate_git_repo_access() -> str | None:
    try:
        subprocess.run(
            GIT_ACCESS_COMMAND,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return "Git repository is not accessible: git executable not found"
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        detail = f": {stderr}" if stderr else ""
        return f"Git repository is not accessible{detail}"

    return None
