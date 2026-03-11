"""Tests for DAG executor — aiw run command (TASK-039)."""
from __future__ import annotations

import json
import threading
import time
import unittest.mock as mock
from pathlib import Path
from typing import Any

import pytest
import yaml

from aiw.cli.run_cmd import run
from aiw.orchestrator.dag_executor import (
    DagExecutionError,
    DagExecutor,
    DagRunResult,
    run_dag,
)
from aiw.orchestrator.executor import ExecutionResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(
    task_id: str,
    depends_on: list[str] | None = None,
    filescope: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": task_id,
        "title": f"Task {task_id}",
        "type": "IMPLEMENTATION",
        "depends_on": depends_on or [],
        "filescope": filescope or [f"aiw/{task_id.lower()}.py"],
        "tests": [],
        "acceptance": [],
    }


def _write_dag(dag_path: Path, tasks: list[dict[str, Any]]) -> None:
    dag_path.write_text(yaml.dump({"tasks": tasks}), encoding="utf-8")


def _write_completed(completed_path: Path, task_ids: set[str]) -> None:
    lines = [
        "| Task ID | Run ID | Completed At (UTC) | Result | Notes |",
        "|---|---|---|---|---|",
    ]
    for task_id in sorted(task_ids):
        lines.append(f"| {task_id} | N/A | 2026-01-01T00:00:00Z | PASS | done |")
    completed_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _pass_result(task_id: str) -> ExecutionResult:
    return ExecutionResult(status="PASS", run_id=f"run-{task_id}")


def _block_result(task_id: str) -> ExecutionResult:
    return ExecutionResult(status="BLOCKED", run_id=f"run-{task_id}")


def _make_executor(
    tmp_path: Path,
    tasks: list[dict[str, Any]],
    completed: set[str] | None = None,
    task_runner: Any = None,
) -> DagExecutor:
    dag_path = tmp_path / "DAG.yml"
    _write_dag(dag_path, tasks)
    completed_path = tmp_path / "COMPLETED.md"
    if completed:
        _write_completed(completed_path, completed)
    (tmp_path / ".aiw" / "runs").mkdir(parents=True, exist_ok=True)
    return DagExecutor(dag_path, completed_path, tmp_path, task_runner=task_runner)


def _setup_run_dag_root(tmp_path: Path, state: str = "PLANNED") -> Path:
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    (root / ".git").mkdir()
    aiw_dir = root / ".aiw"
    aiw_dir.mkdir()
    (aiw_dir / "runs").mkdir()
    state_data = json.dumps(
        {"current_state": state, "state": state}, indent=2
    ) + "\n"
    (aiw_dir / "workflow_state.json").write_text(state_data, encoding="utf-8")
    (root / "docs" / "tasks").mkdir(parents=True)
    (root / "docs" / "constraints.yml").write_text(
        Path("docs/constraints.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    dag_path = root / "docs" / "tasks" / "DAG.yml"
    _write_dag(dag_path, [_make_task("TASK-001")])
    completed_path = root / "docs" / "tasks" / "COMPLETED.md"
    completed_path.write_text(
        "| Task ID | Run ID | ... |\n|---|---|---|\n",
        encoding="utf-8",
    )
    return root


def _read_dag_events(tmp_path: Path) -> list[dict[str, Any]]:
    trace_files = list((tmp_path / ".aiw" / "runs").glob("dag-*.jsonl"))
    if not trace_files:
        return []
    events: list[dict[str, Any]] = []
    for tf in trace_files:
        for line in tf.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events


# ---------------------------------------------------------------------------
# _compute_ready_set
# ---------------------------------------------------------------------------

class TestComputeReadySet:
    def test_empty_dag_returns_no_layers(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, [])
        assert executor._compute_ready_set(set()) == []

    def test_single_task_no_deps(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, [_make_task("TASK-001")])
        layers = executor._compute_ready_set(set())
        assert layers == [["TASK-001"]]

    def test_dependency_chain_gives_sequential_layers(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, [
            _make_task("TASK-001"),
            _make_task("TASK-002", depends_on=["TASK-001"]),
            _make_task("TASK-003", depends_on=["TASK-002"]),
        ])
        layers = executor._compute_ready_set(set())
        assert layers == [["TASK-001"], ["TASK-002"], ["TASK-003"]]

    def test_independent_tasks_placed_in_same_layer(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, [
            _make_task("TASK-001"),
            _make_task("TASK-002"),
        ])
        layers = executor._compute_ready_set(set())
        assert len(layers) == 1
        assert set(layers[0]) == {"TASK-001", "TASK-002"}

    def test_passed_tasks_excluded_from_layers(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, [
            _make_task("TASK-001"),
            _make_task("TASK-002", depends_on=["TASK-001"]),
        ])
        layers = executor._compute_ready_set({"TASK-001"})
        assert layers == [["TASK-002"]]

    def test_all_passed_returns_empty(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, [
            _make_task("TASK-001"),
            _make_task("TASK-002", depends_on=["TASK-001"]),
        ])
        assert executor._compute_ready_set({"TASK-001", "TASK-002"}) == []

    def test_diamond_dependency(self, tmp_path: Path) -> None:
        # A → B, A → C, B → D, C → D
        executor = _make_executor(tmp_path, [
            _make_task("TASK-A"),
            _make_task("TASK-B", depends_on=["TASK-A"]),
            _make_task("TASK-C", depends_on=["TASK-A"]),
            _make_task("TASK-D", depends_on=["TASK-B", "TASK-C"]),
        ])
        layers = executor._compute_ready_set(set())
        assert layers[0] == ["TASK-A"]
        assert set(layers[1]) == {"TASK-B", "TASK-C"}
        assert layers[2] == ["TASK-D"]


# ---------------------------------------------------------------------------
# _has_filescope_collision
# ---------------------------------------------------------------------------

class TestFilescopeCollision:
    def test_no_collision_with_distinct_files(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, [
            _make_task("TASK-001", filescope=["aiw/foo.py"]),
            _make_task("TASK-002", filescope=["aiw/bar.py"]),
        ])
        assert not executor._has_filescope_collision("TASK-001", "TASK-002")

    def test_collision_with_shared_file(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, [
            _make_task("TASK-001", filescope=["aiw/shared.py", "aiw/extra.py"]),
            _make_task("TASK-002", filescope=["aiw/shared.py"]),
        ])
        assert executor._has_filescope_collision("TASK-001", "TASK-002")

    def test_unknown_task_id_returns_no_collision(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, [_make_task("TASK-001")])
        assert not executor._has_filescope_collision("TASK-001", "TASK-999")


# ---------------------------------------------------------------------------
# DagExecutor.run() — full execution
# ---------------------------------------------------------------------------

class TestDagExecutorRun:
    def test_all_tasks_pass_returns_complete(self, tmp_path: Path) -> None:
        call_order: list[str] = []

        def fake_runner(task_id: str, root: Path) -> ExecutionResult:
            call_order.append(task_id)
            return _pass_result(task_id)

        executor = _make_executor(tmp_path, [
            _make_task("TASK-001"),
            _make_task("TASK-002", depends_on=["TASK-001"]),
        ], task_runner=fake_runner)

        result = executor.run()

        assert result.status == "COMPLETE"
        assert "TASK-001" in result.passed
        assert "TASK-002" in result.passed
        assert result.blocked == []
        # Topological order preserved
        assert call_order.index("TASK-001") < call_order.index("TASK-002")

    def test_blocked_task_returns_paused(self, tmp_path: Path) -> None:
        def fake_runner(task_id: str, root: Path) -> ExecutionResult:
            return _block_result(task_id)

        executor = _make_executor(tmp_path, [_make_task("TASK-001")],
                                  task_runner=fake_runner)
        result = executor.run()

        assert result.status == "PAUSED"
        assert "TASK-001" in result.blocked
        assert result.passed == []

    def test_blocked_dependent_not_run(self, tmp_path: Path) -> None:
        called: list[str] = []

        def fake_runner(task_id: str, root: Path) -> ExecutionResult:
            called.append(task_id)
            if task_id == "TASK-001":
                return _block_result(task_id)
            return _pass_result(task_id)

        executor = _make_executor(tmp_path, [
            _make_task("TASK-001"),
            _make_task("TASK-002", depends_on=["TASK-001"]),
        ], task_runner=fake_runner)
        result = executor.run()

        assert result.status == "PAUSED"
        assert "TASK-002" not in called

    def test_completed_tasks_not_re_executed(self, tmp_path: Path) -> None:
        called: list[str] = []

        def fake_runner(task_id: str, root: Path) -> ExecutionResult:
            called.append(task_id)
            return _pass_result(task_id)

        executor = _make_executor(tmp_path, [
            _make_task("TASK-001"),
            _make_task("TASK-002", depends_on=["TASK-001"]),
        ], completed={"TASK-001"}, task_runner=fake_runner)

        result = executor.run()
        assert result.status == "COMPLETE"
        assert "TASK-001" not in called  # already in COMPLETED.md
        assert "TASK-002" in called

    def test_resume_skips_already_passed_tasks(self, tmp_path: Path) -> None:
        called: list[str] = []

        def fake_runner(task_id: str, root: Path) -> ExecutionResult:
            called.append(task_id)
            return _pass_result(task_id)

        executor = _make_executor(tmp_path, [
            _make_task("TASK-001"),
            _make_task("TASK-002", depends_on=["TASK-001"]),
        ], completed={"TASK-001"}, task_runner=fake_runner)

        result = executor.resume()
        assert result.status == "COMPLETE"
        assert "TASK-001" not in called
        assert "TASK-002" in called


# ---------------------------------------------------------------------------
# AC 2: Independent layer tasks run concurrently
# ---------------------------------------------------------------------------

class TestConcurrentExecution:
    def test_independent_tasks_run_concurrently(self, tmp_path: Path) -> None:
        active: list[int] = []
        max_concurrent: list[int] = [0]
        lock = threading.Lock()

        def fake_runner(task_id: str, root: Path) -> ExecutionResult:
            with lock:
                active.append(1)
                max_concurrent[0] = max(max_concurrent[0], len(active))
            time.sleep(0.05)
            with lock:
                active.pop()
            return _pass_result(task_id)

        executor = _make_executor(tmp_path, [
            _make_task("TASK-001", filescope=["aiw/foo.py"]),
            _make_task("TASK-002", filescope=["aiw/bar.py"]),
        ], task_runner=fake_runner)
        result = executor.run()

        assert result.status == "COMPLETE"
        assert max_concurrent[0] == 2  # both ran simultaneously

    def test_filescope_collision_tasks_serialized(self, tmp_path: Path) -> None:
        call_order: list[str] = []
        active: list[int] = []
        max_concurrent: list[int] = [0]
        lock = threading.Lock()

        def fake_runner(task_id: str, root: Path) -> ExecutionResult:
            with lock:
                active.append(1)
                max_concurrent[0] = max(max_concurrent[0], len(active))
            call_order.append(task_id)
            time.sleep(0.02)
            with lock:
                active.pop()
            return _pass_result(task_id)

        executor = _make_executor(tmp_path, [
            _make_task("TASK-001", filescope=["aiw/shared.py"]),
            _make_task("TASK-002", filescope=["aiw/shared.py"]),
        ], task_runner=fake_runner)
        result = executor.run()

        assert result.status == "COMPLETE"
        assert set(call_order) == {"TASK-001", "TASK-002"}
        assert max_concurrent[0] == 1  # never ran concurrently


# ---------------------------------------------------------------------------
# AC 7: All five DAG trace events emitted
# ---------------------------------------------------------------------------

class TestDagTraceEvents:
    def test_complete_run_emits_run_started_layer_started_run_complete(
        self, tmp_path: Path
    ) -> None:
        executor = _make_executor(tmp_path, [_make_task("TASK-001")],
                                  task_runner=lambda tid, r: _pass_result(tid))
        executor.run()

        events = _read_dag_events(tmp_path)
        event_types = [e["event_type"] for e in events]
        assert "dag_run_started" in event_types
        assert "dag_layer_started" in event_types
        assert "dag_run_complete" in event_types
        # blocked events should NOT appear
        assert "dag_task_blocked" not in event_types
        assert "dag_run_paused" not in event_types

    def test_blocked_run_emits_task_blocked_and_paused(
        self, tmp_path: Path
    ) -> None:
        executor = _make_executor(tmp_path, [_make_task("TASK-001")],
                                  task_runner=lambda tid, r: _block_result(tid))
        executor.run()

        events = _read_dag_events(tmp_path)
        event_types = [e["event_type"] for e in events]
        assert "dag_run_started" in event_types
        assert "dag_layer_started" in event_types
        assert "dag_task_blocked" in event_types
        assert "dag_run_paused" in event_types
        assert "dag_run_complete" not in event_types

    def test_all_events_carry_run_id(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, [_make_task("TASK-001")],
                                  task_runner=lambda tid, r: _pass_result(tid))
        executor.run()

        events = _read_dag_events(tmp_path)
        assert events, "no events emitted"
        run_id = events[0]["run_id"]
        assert all(e["run_id"] == run_id for e in events)

    def test_dag_run_started_payload(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, [
            _make_task("TASK-001"),
            _make_task("TASK-002"),
        ], task_runner=lambda tid, r: _pass_result(tid))
        executor.run()

        events = _read_dag_events(tmp_path)
        started = next(e for e in events if e["event_type"] == "dag_run_started")
        assert started["payload"]["total_tasks"] == 2
        assert started["payload"]["layer_count"] == 1

    def test_dag_task_blocked_payload_contains_blocker_path(
        self, tmp_path: Path
    ) -> None:
        executor = _make_executor(tmp_path, [_make_task("TASK-001")],
                                  task_runner=lambda tid, r: _block_result(tid))
        executor.run()

        events = _read_dag_events(tmp_path)
        blocked_event = next(e for e in events if e["event_type"] == "dag_task_blocked")
        assert blocked_event["payload"]["task_id"] == "TASK-001"
        assert "blocker_report_path" in blocked_event["payload"]


# ---------------------------------------------------------------------------
# run_dag() — state enforcement and CLI entry
# ---------------------------------------------------------------------------

class TestRunDag:
    def test_refused_when_state_not_planned(self, tmp_path: Path) -> None:
        for state in ("BLOCKED", "EXECUTING", "INIT", "CONSTRAINTS_APPROVED"):
            root = _setup_run_dag_root(tmp_path / state, state=state)
            with pytest.raises(DagExecutionError, match="PLANNED state"):
                run_dag(root)

    def test_proceeds_when_state_is_planned(self, tmp_path: Path) -> None:
        root = _setup_run_dag_root(tmp_path, state="PLANNED")

        def fake_runner(task_id: str, r: Path) -> ExecutionResult:
            return _pass_result(task_id)

        executor_seen: list[DagExecutor] = []
        original_init = DagExecutor.__init__

        def patched_init(
            self: DagExecutor,
            dag_path: Path,
            completed_path: Path,
            root_p: Path,
            *,
            task_runner: Any = None,
        ) -> None:
            original_init(
                self, dag_path, completed_path, root_p, task_runner=fake_runner
            )
            executor_seen.append(self)

        with mock.patch.object(DagExecutor, "__init__", patched_init):
            result = run_dag(root)

        assert result.status == "COMPLETE"

    def test_resume_flag_calls_resume_method(self, tmp_path: Path) -> None:
        root = _setup_run_dag_root(tmp_path, state="PLANNED")

        fake_result = DagRunResult(
            status="COMPLETE", passed=[], blocked=[], summary="ok"
        )
        with mock.patch.object(DagExecutor, "resume", return_value=fake_result) as m:
            result = run_dag(root, resume=True)

        m.assert_called_once()
        assert result.status == "COMPLETE"

    def test_no_resume_calls_run_method(self, tmp_path: Path) -> None:
        root = _setup_run_dag_root(tmp_path, state="PLANNED")

        fake_result = DagRunResult(
            status="COMPLETE", passed=[], blocked=[], summary="ok"
        )
        with mock.patch.object(DagExecutor, "run", return_value=fake_result) as m:
            result = run_dag(root, resume=False)

        m.assert_called_once()
        assert result.status == "COMPLETE"


# ---------------------------------------------------------------------------
# run_cmd.run() wrapper
# ---------------------------------------------------------------------------

class TestRunCmdWrapper:
    def test_run_cmd_delegates_to_run_dag(self, tmp_path: Path) -> None:
        root = _setup_run_dag_root(tmp_path, state="PLANNED")

        fake_result = DagRunResult(
            status="COMPLETE", passed=[], blocked=[], summary="ok"
        )
        with mock.patch(
            "aiw.cli.run_cmd.run_dag", return_value=fake_result
        ) as m:
            result = run(root, resume=False)

        m.assert_called_once_with(root, resume=False)
        assert result is fake_result

    def test_run_cmd_resume_delegates_with_resume_true(self, tmp_path: Path) -> None:
        root = _setup_run_dag_root(tmp_path, state="PLANNED")

        fake_result = DagRunResult(
            status="PAUSED", passed=[], blocked=["TASK-001"], summary="paused"
        )
        with mock.patch(
            "aiw.cli.run_cmd.run_dag", return_value=fake_result
        ) as m:
            result = run(root, resume=True)

        m.assert_called_once_with(root, resume=True)
        assert result is fake_result
