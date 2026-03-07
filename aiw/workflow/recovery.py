"""Startup recovery for stale EXECUTING workflow state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiw.infra.constraints import ConstraintsConfig, load_constraints
from aiw.infra.trace import TraceEmitter
from aiw.workflow.state_machine import WorkflowStateMachine


def check_stale_execution(state_path: Path) -> bool:
    """Return ``True`` when startup finds a stale EXECUTING state."""
    constraints = _load_repo_constraints(state_path)
    if not constraints.execution.stale_execution_policy.enabled:
        return False
    return _read_current_state(state_path) == "EXECUTING"


def recover_stale_execution(state_path: Path) -> None:
    """Transition stale EXECUTING state to BLOCKED and emit recovery events."""
    constraints = _load_repo_constraints(state_path)
    policy = constraints.execution.stale_execution_policy
    if not policy.enabled:
        return

    payload = _read_state_payload(state_path)
    current_state = _extract_current_state(payload)
    if current_state != "EXECUTING":
        return

    transition_command = f"on:{policy.on_detect_executing_at_startup.emit_event}"
    machine = WorkflowStateMachine(current_state=current_state)
    next_state = machine.transition(transition_command)
    if next_state != policy.on_detect_executing_at_startup.transition_to:
        raise ValueError(
            "stale execution recovery transition does not match configured target state"
        )

    payload["current_state"] = next_state
    payload["state"] = next_state
    _write_state_payload(state_path, payload)

    repo_root = _repo_root_from_state_path(state_path)
    run_id = str(payload.get("run_id") or "stale-execution-recovery")
    trace_path = _trace_path(repo_root, constraints)

    _emit_unchecked_event(
        trace_path,
        run_id,
        policy.on_detect_executing_at_startup.emit_event,
        {
            "from_state": current_state,
            "to_state": next_state,
            "state_file": _relative_to_repo(repo_root, state_path),
        },
    )
    TraceEmitter(run_id=run_id, output_path=trace_path).emit(
        "state_transition",
        {
            "from_state": current_state,
            "to_state": next_state,
            "trigger": transition_command,
        },
    )


def _load_repo_constraints(state_path: Path) -> ConstraintsConfig:
    repo_root = _repo_root_from_state_path(state_path)
    return load_constraints(repo_root / "docs" / "constraints.yml")


def _repo_root_from_state_path(state_path: Path) -> Path:
    return state_path.resolve().parent.parent


def _read_current_state(state_path: Path) -> str:
    return _extract_current_state(_read_state_payload(state_path))


def _read_state_payload(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}

    data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("workflow state file must contain a JSON object")
    return data


def _extract_current_state(payload: dict[str, Any]) -> str:
    for key in ("current_state", "state"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    raise ValueError(
        "workflow state file missing string field 'current_state' or 'state'"
    )


def _write_state_payload(state_path: Path, payload: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _trace_path(repo_root: Path, constraints: ConstraintsConfig) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    template = constraints.observability.artifacts.jsonl_trace_path
    return repo_root / template.replace("<timestamp>", timestamp)


def _emit_unchecked_event(
    output_path: Path,
    run_id: str,
    event_type: str,
    payload: dict[str, object],
) -> None:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "run_id": run_id,
        "payload": payload,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as trace_file:
        trace_file.write(json.dumps(event, sort_keys=True) + "\n")


def _relative_to_repo(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root).as_posix()
