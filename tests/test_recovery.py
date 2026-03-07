"""Tests for stale EXECUTING startup recovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aiw.workflow.recovery import check_stale_execution, recover_stale_execution


def test_check_stale_execution_detects_executing_state_on_startup(
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    state_path = repo_root / ".aiw" / "workflow_state.json"
    _write_state(
        state_path,
        {
            "current_state": "EXECUTING",
            "metadata": {"run_id": "run-123"},
            "state": "EXECUTING",
        },
    )

    assert check_stale_execution(state_path) is True


def test_recover_stale_execution_transitions_to_blocked_and_emits_event(
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    state_path = repo_root / ".aiw" / "workflow_state.json"
    _write_state(
        state_path,
        {
            "current_state": "EXECUTING",
            "metadata": {"run_id": "run-123"},
            "state": "EXECUTING",
        },
    )

    recover_stale_execution(state_path)

    state = _read_state(state_path)
    assert state["current_state"] == "BLOCKED"
    assert state["state"] == "BLOCKED"
    assert state.get("metadata", {}).get("run_id") == "run-123"

    trace_files = sorted((repo_root / ".aiw" / "runs").glob("*.jsonl"))
    assert len(trace_files) == 1
    events = _read_events(trace_files[0])
    assert [event["event_type"] for event in events] == [
        "stale_execution_detected",
        "state_transition",
    ]
    assert all(event["run_id"] == "run-123" for event in events)
    assert events[0]["payload"] == {
        "from_state": "EXECUTING",
        "state_file": ".aiw/workflow_state.json",
        "to_state": "BLOCKED",
    }
    assert events[1]["payload"] == {
        "from_state": "EXECUTING",
        "to_state": "BLOCKED",
        "trigger": "on:stale_execution_detected",
    }


def test_recover_stale_execution_is_noop_when_state_is_not_executing(
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    state_path = repo_root / ".aiw" / "workflow_state.json"
    _write_state(
        state_path,
        {
            "current_state": "PLANNED",
            "metadata": {"run_id": "run-123"},
            "state": "PLANNED",
        },
    )

    recover_stale_execution(state_path)

    assert _read_state(state_path)["current_state"] == "PLANNED"
    assert list((repo_root / ".aiw" / "runs").glob("*.jsonl")) == []


def test_check_and_recover_ignore_stale_state_when_policy_disabled(
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path, stale_policy_enabled=False)
    state_path = repo_root / ".aiw" / "workflow_state.json"
    _write_state(
        state_path,
        {
            "current_state": "EXECUTING",
            "metadata": {"run_id": "run-123"},
            "state": "EXECUTING",
        },
    )

    assert check_stale_execution(state_path) is False

    recover_stale_execution(state_path)

    assert _read_state(state_path)["current_state"] == "EXECUTING"
    assert list((repo_root / ".aiw" / "runs").glob("*.jsonl")) == []


def _init_repo(tmp_path: Path, *, stale_policy_enabled: bool = True) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "docs").mkdir(parents=True)
    (repo_root / ".aiw" / "runs").mkdir(parents=True)

    constraints_text = Path("docs/constraints.yml").read_text(encoding="utf-8")
    if not stale_policy_enabled:
        constraints_text = constraints_text.replace(
            "  stale_execution_policy:\n    enabled: true\n",
            "  stale_execution_policy:\n    enabled: false\n",
        )
    (repo_root / "docs" / "constraints.yml").write_text(
        constraints_text,
        encoding="utf-8",
    )

    return repo_root


def _write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_state(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("workflow state payload must be a JSON object")
    return payload


def _read_events(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
