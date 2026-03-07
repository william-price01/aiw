"""End-to-end integration tests for error and BLOCKED execution paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aiw.cli.main import main
from aiw.orchestrator.coder import DiffStats, PatchResult, PatchValidationError
from aiw.orchestrator.decompose import run_decompose
from aiw.orchestrator.executor import ExecutionError
from aiw.orchestrator.executor import TestRunResult as ExecutorTestRunResult
from aiw.workflow.gates import ConstraintsGateError

INVALID_TRANSITION_CASES = [
    ("INIT", ["approve-prd"]),
    ("PRD_DRAFT", ["sdd"]),
    ("PRD_APPROVED", ["approve-prd"]),
    ("SDD_DRAFT", ["adrs"]),
    ("SDD_APPROVED", ["approve-sdd"]),
    ("ADRS_DRAFT", ["constraints"]),
    ("ADRS_APPROVED", ["approve-adrs"]),
    ("CONSTRAINTS_DRAFT", ["decompose"]),
    ("CONSTRAINTS_APPROVED", ["go", "TASK-001"]),
    ("PLANNED", ["approve-constraints"]),
    ("BLOCKED", ["go", "TASK-001"]),
]


@pytest.mark.parametrize(("state", "argv"), INVALID_TRANSITION_CASES)
def test_invalid_state_transitions_are_rejected_across_workflow(
    integration_repo_factory: Any,
    state: str,
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = integration_repo_factory(state=state)

    result = main(argv, root=repo.root)

    captured = capsys.readouterr()
    assert result == 1
    assert repo.read_state()["current_state"] == state
    assert f"state {state!r}" in captured.err


def test_execution_exhaustion_transitions_to_blocked_and_generates_blocker_report(
    integration_repo_factory: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = integration_repo_factory()

    monkeypatch.setattr(
        "aiw.orchestrator.executor.run_coder_session",
        lambda task_spec, constraints, repo_root=None, codex_runner=None: PatchResult(
            changed_files=("aiw/example.py",),
            diff_stats=DiffStats(files_changed=1, lines_changed=2),
            success=True,
            patch="",
        ),
    )
    monkeypatch.setattr(
        "aiw.orchestrator.executor.run_fixer_session",
        lambda task_spec, test_output, constraints, repo_root=None, codex_runner=None: (
            PatchResult(
                changed_files=("aiw/example.py",),
                diff_stats=DiffStats(files_changed=1, lines_changed=2),
                success=True,
                patch="",
            )
        ),
    )
    monkeypatch.setattr(
        "aiw.orchestrator.executor._apply_patch", lambda patch, root: None
    )
    test_results = [
        ExecutorTestRunResult(
            passed=False,
            output="1 failed\nassert VALUE == 2\n",
            exit_code=1,
        ),
        ExecutorTestRunResult(
            passed=False,
            output="1 failed\nassert VALUE == 2\n",
            exit_code=1,
        ),
    ]

    def failing_run_tests(
        repo_root: Path,
        constraints: object,
        trace: Any,
        task_id: str,
        iteration: int,
    ) -> ExecutorTestRunResult:
        del repo_root, constraints
        trace.emit(
            "test_run_started",
            {"task_id": task_id, "iteration": iteration, "command": ["pytest", "-q"]},
        )
        return test_results.pop(0)

    monkeypatch.setattr(
        "aiw.orchestrator.executor._run_tests",
        failing_run_tests,
    )

    assert main(["go", repo.task_id], root=repo.root) == 0

    state = repo.read_state()
    assert state["current_state"] == "BLOCKED"

    report_path = repo.root / "docs" / "reports" / f"{repo.task_id}_blocker_report.md"
    assert report_path.is_file()
    report = report_path.read_text(encoding="utf-8")
    assert f"- Task ID: {repo.task_id}" in report
    assert "- Failure reason: iteration_exhausted" in report

    events = repo.read_trace_events()
    event_types = [event["event_type"] for event in events]
    assert event_types == [
        "constraint_validation",
        "state_transition",
        "scope_validation",
        "diff_threshold_check",
        "test_run_started",
        "test_run_failed",
        "quality_gate_failed",
        "fixer_spawned",
        "scope_validation",
        "diff_threshold_check",
        "test_run_started",
        "test_run_failed",
        "quality_gate_failed",
        "iteration_exhausted",
        "state_transition",
        "blocked",
        "run_complete",
    ]
    assert _event(events, "blocked")["payload"] == {
        "task_id": repo.task_id,
        "reason": "iteration_exhausted",
        "iterations_used": 3,
    }


def test_locked_artifact_modification_is_rejected_during_execution(
    integration_repo_factory: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = integration_repo_factory()

    monkeypatch.setattr(
        "aiw.orchestrator.executor.run_coder_session",
        lambda task_spec, constraints, repo_root=None, codex_runner=None: PatchResult(
            changed_files=("docs/tasks/DAG.md",),
            diff_stats=DiffStats(files_changed=1, lines_changed=4),
            success=True,
            patch="diff --git a/docs/tasks/DAG.md b/docs/tasks/DAG.md\n",
        ),
    )
    monkeypatch.setattr(
        "aiw.orchestrator.executor._apply_patch", lambda patch, root: None
    )

    with pytest.raises(ExecutionError, match="Locked artifact modification detected"):
        main(["go", repo.task_id], root=repo.root)

    events = repo.read_trace_events()
    assert [event["event_type"] for event in events] == [
        "constraint_validation",
        "state_transition",
        "lock_violation_hard_fail",
    ]
    assert _event(events, "lock_violation_hard_fail")["payload"] == {
        "task_id": repo.task_id,
        "phase": "coder",
        "violations": ["docs/tasks/DAG.md"],
    }


def test_diff_threshold_exceeded_is_rejected_and_blocks_run(
    integration_repo_factory: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = integration_repo_factory()

    def raise_diff_violation(
        task_spec: object,
        constraints: object,
        repo_root: Path | None = None,
        codex_runner: object | None = None,
    ) -> PatchResult:
        del task_spec, constraints, repo_root, codex_runner
        raise PatchValidationError(
            scope_violations=[],
            diff_violations=["max_lines_changed_exceeded:1501>1500"],
        )

    monkeypatch.setattr(
        "aiw.orchestrator.executor.run_coder_session",
        raise_diff_violation,
    )

    assert main(["go", repo.task_id], root=repo.root) == 0

    assert repo.read_state()["current_state"] == "BLOCKED"
    events = repo.read_trace_events()
    assert [event["event_type"] for event in events] == [
        "constraint_validation",
        "state_transition",
        "scope_validation",
        "diff_threshold_check",
        "state_transition",
        "blocked",
        "run_complete",
    ]
    assert _event(events, "scope_validation")["payload"] == {
        "task_id": repo.task_id,
        "phase": "coder",
        "status": "failed",
        "detail": (
            "Invalid coder patch proposal: "
            "diff violations: max_lines_changed_exceeded:1501>1500"
        ),
    }
    assert _event(events, "diff_threshold_check")["payload"] == {
        "task_id": repo.task_id,
        "phase": "coder",
        "status": "failed",
        "detail": (
            "Invalid coder patch proposal: "
            "diff violations: max_lines_changed_exceeded:1501>1500"
        ),
    }


def test_stale_executing_is_recovered_to_blocked_on_startup(
    integration_repo_factory: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = integration_repo_factory(state="EXECUTING")
    repo.write_state("EXECUTING", metadata={"run_id": "stale-run-123"})

    result = main(
        ["request-change", "docs/prd.md", "--reason", "r", "--impact", "i"],
        root=repo.root,
    )

    captured = capsys.readouterr()
    assert result == 1
    assert repo.read_state()["current_state"] == "BLOCKED"
    assert "stale EXECUTING state detected" in captured.err

    events = repo.read_trace_events()
    assert [event["event_type"] for event in events] == [
        "stale_execution_detected",
        "state_transition",
    ]
    assert all(event["run_id"] == "stale-run-123" for event in events)
    assert _event(events, "state_transition")["payload"] == {
        "from_state": "EXECUTING",
        "to_state": "BLOCKED",
        "trigger": "on:stale_execution_detected",
    }


def test_constraints_gate_refuses_placeholder_values_before_decompose(
    integration_repo_factory: Any,
) -> None:
    repo = integration_repo_factory(state="CONSTRAINTS_APPROVED", test_command="TBD")

    with pytest.raises(ConstraintsGateError) as exc_info:
        run_decompose(repo.root)

    assert exc_info.value.event.event_type == "constraint_validation_failed"
    assert exc_info.value.event.payload == {
        "errors": ["Field quality.test_command contains placeholder value: 'TBD'"],
        "refuse_commands": ["aiw decompose", "aiw go TASK-###"],
    }
    assert not (repo.root / "docs" / "tasks").joinpath("TASK-002.md").exists()


def _event(
    events: list[dict[str, Any]],
    event_type: str,
) -> dict[str, Any]:
    for event in events:
        if event["event_type"] == event_type:
            return event
    raise AssertionError(f"missing event {event_type!r}")
