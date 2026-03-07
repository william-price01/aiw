"""Read-only TUI rendering helpers derived from on-disk AIW artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_TASK_FILE_PATTERN = "TASK-*.md"
_TASK_ID_RE = re.compile(r"^(TASK-\d{3})\.md$")
_COMPLETED_ROW_RE = re.compile(
    r"^\|\s*(TASK-\d{3})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|"
)
_TERMINATION_RE = re.compile(r"^- Termination:\s*`([^`]+)`\s*$", re.MULTILINE)


def render_status(root: Path) -> str:
    """Render the current workflow status from the persisted workflow state."""
    state_path = root / ".aiw" / "workflow_state.json"
    if not state_path.exists():
        return "\n".join(
            [
                "Workflow Status",
                "State: unavailable",
                "Source: missing .aiw/workflow_state.json",
            ]
        )

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    state = _read_state_value(payload)
    metadata = payload.get("metadata") or {}
    run_id = _string_field(metadata, "run_id") if isinstance(metadata, dict) else None

    lines = ["Workflow Status", f"State: {state}"]
    if run_id is not None:
        lines.append(f"Run ID: {run_id}")
    lines.append(f"Source: {state_path.relative_to(root)}")
    return "\n".join(lines)


def render_task_list(root: Path) -> str:
    """Render task statuses strictly from task artifacts on disk."""
    tasks_dir = root / "docs" / "tasks"
    if not tasks_dir.exists():
        return "Task List\nNo task artifacts found."

    completed_statuses = _load_completed_statuses(tasks_dir / "COMPLETED.md")
    task_ids = sorted(_discover_task_ids(tasks_dir))

    if not task_ids:
        return "Task List\nNo task specs found."

    lines = ["Task List"]
    for task_id in task_ids:
        status, source = _derive_task_status(tasks_dir, task_id, completed_statuses)
        lines.append(f"{task_id}: {status} ({source})")
    return "\n".join(lines)


def render_run_trace(run_path: Path) -> str:
    """Render JSONL trace events in file order."""
    if not run_path.exists():
        return f"Run Trace\nSource: missing {run_path}"

    lines = ["Run Trace", f"Source: {run_path}"]
    raw_lines = run_path.read_text(encoding="utf-8").splitlines()
    if not raw_lines:
        lines.append("No trace events found.")
        return "\n".join(lines)

    for index, raw_line in enumerate(raw_lines, start=1):
        if not raw_line.strip():
            continue
        event = json.loads(raw_line)
        timestamp = _string_field(event, "timestamp") or "unknown-timestamp"
        event_type = _string_field(event, "event_type") or "unknown-event"
        payload = event.get("payload")
        rendered_payload = json.dumps(payload, sort_keys=True)
        lines.append(f"{index}. {timestamp} {event_type} {rendered_payload}")

    if len(lines) == 2:
        lines.append("No trace events found.")
    return "\n".join(lines)


def _read_state_value(payload: dict[str, Any]) -> str:
    for key in ("current_state", "state"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return "unknown"


def _string_field(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _discover_task_ids(tasks_dir: Path) -> set[str]:
    task_ids: set[str] = set()
    for path in tasks_dir.glob(_TASK_FILE_PATTERN):
        match = _TASK_ID_RE.match(path.name)
        if match is None:
            continue
        task_ids.add(match.group(1))
    return task_ids


def _load_completed_statuses(completed_path: Path) -> dict[str, str]:
    if not completed_path.exists():
        return {}

    statuses: dict[str, str] = {}
    for line in completed_path.read_text(encoding="utf-8").splitlines():
        match = _COMPLETED_ROW_RE.match(line.strip())
        if match is None:
            continue
        task_id, _, _, result = match.groups()
        statuses[task_id] = result.strip()
    return statuses


def _derive_task_status(
    tasks_dir: Path,
    task_id: str,
    completed_statuses: dict[str, str],
) -> tuple[str, str]:
    log_path = tasks_dir / f"{task_id}.log.md"
    if log_path.exists():
        log_status = _latest_log_termination(log_path)
        if log_status is not None:
            return log_status, log_path.name

    if task_id in completed_statuses:
        return completed_statuses[task_id], "COMPLETED.md"

    return "NOT_RUN", f"{task_id}.md only"


def _latest_log_termination(log_path: Path) -> str | None:
    matches = _TERMINATION_RE.findall(log_path.read_text(encoding="utf-8"))
    if not matches:
        return None
    return str(matches[-1]).strip()
