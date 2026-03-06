"""Structured JSONL trace emission for AIW runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

REQUIRED_TRACE_EVENTS: Final[frozenset[str]] = frozenset(
    {
        "state_transition",
        "constraint_validation",
        "scope_validation",
        "diff_threshold_check",
        "test_run_started",
        "test_run_failed",
        "test_run_passed",
        "fixer_spawned",
        "iteration_exhausted",
        "blocked",
        "run_complete",
        "task_marked_complete",
        "quality_gate_failed",
        "lock_violation_hard_fail",
    }
)


class TraceEmitter:
    """Append structured trace events to a run-specific JSONL file."""

    def __init__(self, run_id: str, output_path: Path) -> None:
        self._run_id = run_id
        self._output_path = output_path

    def emit(self, event_type: str, payload: dict[str, object]) -> None:
        """Append a single trace event to the configured JSONL file."""
        if event_type not in REQUIRED_TRACE_EVENTS:
            raise ValueError(f"Unsupported trace event: {event_type}")

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "run_id": self._run_id,
            "payload": payload,
        }

        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._output_path.open("a", encoding="utf-8") as trace_file:
            trace_file.write(json.dumps(event, sort_keys=True) + "\n")
