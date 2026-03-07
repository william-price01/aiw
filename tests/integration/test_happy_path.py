"""End-to-end happy-path workflow integration tests."""

from __future__ import annotations

import json
from pathlib import Path

from aiw.cli.main import main
from tests.conftest import HappyPathRepo


def test_happy_path_progresses_from_init_through_pass(
    happy_path_repo: HappyPathRepo,
) -> None:
    repo_root = happy_path_repo.root

    assert main(["init"], root=repo_root) == 0
    assert _read_state(repo_root) == {"state": "INIT"}
    assert (repo_root / ".aiw" / "runs").is_dir()

    for argv, expected_state in (
        (["prd"], "PRD_DRAFT"),
        (["approve-prd"], "PRD_APPROVED"),
        (["sdd"], "SDD_DRAFT"),
        (["approve-sdd"], "SDD_APPROVED"),
        (["adrs"], "ADRS_DRAFT"),
        (["approve-adrs"], "ADRS_APPROVED"),
        (["constraints"], "CONSTRAINTS_DRAFT"),
        (["approve-constraints"], "CONSTRAINTS_APPROVED"),
    ):
        assert main(argv, root=repo_root) == 0
        assert _read_state(repo_root)["state"] == expected_state
        assert _read_state(repo_root)["current_state"] == expected_state

    assert (repo_root / "docs" / "prd.md").is_file()
    assert (repo_root / "docs" / "sdd.md").is_file()
    assert (repo_root / "docs" / "adrs" / "ADR-001-test.md").is_file()
    assert (repo_root / "docs" / "constraints.yml").is_file()

    assert main(["decompose"], root=repo_root) == 0
    assert _read_state(repo_root)["state"] == "PLANNED"
    assert (repo_root / "docs" / "tasks" / "DAG.md").is_file()
    assert (repo_root / "docs" / "tasks" / "DAG.yml").is_file()
    assert (repo_root / "docs" / "tasks" / "TASK-001.md").is_file()

    assert main(["go", "TASK-001"], root=repo_root) == 0

    state = _read_state(repo_root)
    assert state["current_state"] == "PLANNED"
    assert happy_path_repo.checkpoint_calls == ["TASK-001 baseline"]

    trace_path = next((repo_root / ".aiw" / "runs").glob("*.jsonl"))
    events = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    run_id = str(events[0]["run_id"])

    completed = (repo_root / "docs" / "tasks" / "COMPLETED.md").read_text(
        encoding="utf-8"
    )
    assert f"| TASK-001 | {run_id} |" in completed
    assert "| PASS | Completed by aiw go |" in completed

    event_types = [event["event_type"] for event in events]

    assert event_types == [
        "constraint_validation",
        "state_transition",
        "scope_validation",
        "diff_threshold_check",
        "test_run_started",
        "test_run_passed",
        "task_marked_complete",
        "state_transition",
        "run_complete",
    ]
    assert events[1]["payload"] == {
        "from_state": "PLANNED",
        "to_state": "EXECUTING",
        "trigger": "aiw go TASK-###",
    }
    assert events[7]["payload"] == {
        "from_state": "EXECUTING",
        "to_state": "PLANNED",
        "trigger": "on:success",
    }
    assert all(event["run_id"] == run_id for event in events)


def _read_state(repo_root: Path) -> dict[str, str]:
    state_path = repo_root / ".aiw" / "workflow_state.json"
    data = json.loads(state_path.read_text(encoding="utf-8"))
    return {key: str(value) for key, value in data.items()}
