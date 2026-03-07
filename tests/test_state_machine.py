"""Tests for the AIW core workflow state machine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiw.workflow import (
    TRANSITIONS,
    WORKFLOW_STATES,
    IllegalStateTransitionError,
    WorkflowStateMachine,
)

EXPECTED_STATES = {
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
}

ALL_TRANSITIONS = [
    ("INIT", "aiw prd", "PRD_DRAFT"),
    ("PRD_DRAFT", "aiw approve-prd", "PRD_APPROVED"),
    ("PRD_APPROVED", "aiw sdd", "SDD_DRAFT"),
    ("SDD_DRAFT", "aiw approve-sdd", "SDD_APPROVED"),
    ("SDD_APPROVED", "aiw adrs", "ADRS_DRAFT"),
    ("ADRS_DRAFT", "aiw approve-adrs", "ADRS_APPROVED"),
    ("ADRS_APPROVED", "aiw constraints", "CONSTRAINTS_DRAFT"),
    ("CONSTRAINTS_DRAFT", "aiw approve-constraints", "CONSTRAINTS_APPROVED"),
    ("CONSTRAINTS_APPROVED", "aiw decompose", "PLANNED"),
    ("PLANNED", "aiw go TASK-###", "EXECUTING"),
    ("EXECUTING", "on:success", "PLANNED"),
    ("EXECUTING", "on:exhaustion", "BLOCKED"),
    ("EXECUTING", "on:scope_violation_second", "BLOCKED"),
    ("EXECUTING", "on:oversized_split", "BLOCKED"),
    ("EXECUTING", "on:abort", "PLANNED"),
    ("EXECUTING", "on:stale_execution_detected", "BLOCKED"),
]


def test_all_12_states_are_present() -> None:
    assert len(WORKFLOW_STATES) == 12
    assert set(WORKFLOW_STATES) == EXPECTED_STATES


@pytest.mark.parametrize(("start_state", "action", "expected_state"), ALL_TRANSITIONS)
def test_all_defined_transitions_succeed(
    start_state: str,
    action: str,
    expected_state: str,
) -> None:
    machine = WorkflowStateMachine(current_state=start_state)

    assert machine.transition(action) == expected_state
    assert machine.current_state == expected_state


def test_transition_table_matches_spec_cases() -> None:
    assert len(TRANSITIONS) == len(ALL_TRANSITIONS)


def test_invalid_transition_raises_hard_failure() -> None:
    machine = WorkflowStateMachine(current_state="INIT")

    with pytest.raises(IllegalStateTransitionError):
        machine.transition("aiw sdd")


def test_state_round_trip_json(tmp_path: Path) -> None:
    state_path = tmp_path / ".aiw" / "workflow_state.json"
    machine = WorkflowStateMachine(current_state="PLANNED")

    machine.save(state_path)
    reloaded = WorkflowStateMachine.load(state_path)

    assert reloaded.current_state == "PLANNED"


def test_load_missing_state_file_defaults_to_init(tmp_path: Path) -> None:
    state_path = tmp_path / "missing" / "workflow_state.json"

    machine = WorkflowStateMachine.load(state_path)

    assert machine.current_state == "INIT"


def test_metadata_round_trip_in_memory() -> None:
    machine = WorkflowStateMachine(metadata={"run_id": "abc"})

    assert machine.get_metadata("run_id") == "abc"

    machine.set_metadata("run_id", "xyz")

    assert machine.get_metadata("run_id") == "xyz"


def test_save_includes_metadata_when_non_empty(tmp_path: Path) -> None:
    state_path = tmp_path / ".aiw" / "workflow_state.json"
    machine = WorkflowStateMachine(
        current_state="EXECUTING",
        metadata={"run_id": "abc"},
    )

    machine.save(state_path)

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload == {
        "current_state": "EXECUTING",
        "metadata": {"run_id": "abc"},
    }


def test_save_omits_metadata_when_empty(tmp_path: Path) -> None:
    state_path = tmp_path / ".aiw" / "workflow_state.json"
    machine = WorkflowStateMachine(current_state="PLANNED")

    machine.save(state_path)

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload == {"current_state": "PLANNED"}
    assert "metadata" not in payload


def test_load_deserializes_metadata(tmp_path: Path) -> None:
    state_path = tmp_path / ".aiw" / "workflow_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {"current_state": "EXECUTING", "metadata": {"run_id": "abc"}},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    machine = WorkflowStateMachine.load(state_path)

    assert machine.current_state == "EXECUTING"
    assert machine.get_metadata("run_id") == "abc"


def test_load_without_metadata_defaults_to_empty_metadata(tmp_path: Path) -> None:
    state_path = tmp_path / ".aiw" / "workflow_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"current_state": "PLANNED"}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    machine = WorkflowStateMachine.load(state_path)

    assert machine.current_state == "PLANNED"
    assert machine.get_metadata("run_id") is None


def test_load_with_non_dict_metadata_falls_back_to_empty_metadata(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / ".aiw" / "workflow_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {"current_state": "EXECUTING", "metadata": "abc"},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    machine = WorkflowStateMachine.load(state_path)

    assert machine.current_state == "EXECUTING"
    assert machine.get_metadata("run_id") is None
