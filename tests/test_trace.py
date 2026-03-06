"""Tests for structured JSONL trace emission."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiw.infra.trace import REQUIRED_TRACE_EVENTS, TraceEmitter


def test_trace_emitter_writes_valid_jsonl_with_required_fields(tmp_path: Path) -> None:
    output_path = tmp_path / ".aiw" / "runs" / "run-20260305T120000Z.jsonl"
    emitter = TraceEmitter(run_id="run-123", output_path=output_path)

    emitter.emit("state_transition", {"from_state": "PLANNED", "to_state": "EXECUTING"})

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    event = json.loads(lines[0])
    assert event["event_type"] == "state_transition"
    assert event["run_id"] == "run-123"
    assert event["payload"] == {"from_state": "PLANNED", "to_state": "EXECUTING"}
    assert isinstance(event["timestamp"], str)


def test_trace_emitter_supports_all_required_event_types(tmp_path: Path) -> None:
    output_path = tmp_path / ".aiw" / "runs" / "run-20260305T120000Z.jsonl"
    emitter = TraceEmitter(run_id="run-456", output_path=output_path)

    for event_type in sorted(REQUIRED_TRACE_EVENTS):
        emitter.emit(event_type, {"event": event_type})

    events = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]

    assert {event["event_type"] for event in events} == REQUIRED_TRACE_EVENTS
    assert all(event["run_id"] == "run-456" for event in events)
    assert all(
        set(event) == {"timestamp", "event_type", "run_id", "payload"}
        for event in events
    )


def test_trace_emitter_is_append_only_within_a_run(tmp_path: Path) -> None:
    output_path = tmp_path / ".aiw" / "runs" / "run-20260305T120000Z.jsonl"
    emitter = TraceEmitter(run_id="run-789", output_path=output_path)

    emitter.emit("test_run_started", {"command": "pytest -q"})
    first_size = output_path.stat().st_size

    emitter.emit("test_run_passed", {"exit_code": 0})
    lines = output_path.read_text(encoding="utf-8").splitlines()

    assert output_path.stat().st_size > first_size
    assert len(lines) == 2
    assert json.loads(lines[0])["event_type"] == "test_run_started"
    assert json.loads(lines[1])["event_type"] == "test_run_passed"


def test_trace_emitter_rejects_unsupported_event_type(tmp_path: Path) -> None:
    output_path = tmp_path / ".aiw" / "runs" / "run-20260305T120000Z.jsonl"
    emitter = TraceEmitter(run_id="run-999", output_path=output_path)

    with pytest.raises(ValueError, match="Unsupported trace event"):
        emitter.emit("not_in_spec", {"invalid": True})
