"""DAG executor — topological walk of DAG.yml with layer parallelism."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, cast
from uuid import uuid4

import yaml

from aiw.infra import load_constraints
from aiw.orchestrator.executor import ExecutionResult, execute_task
from aiw.workflow import WorkflowStateMachine

TaskRunner = Callable[[str, Path], ExecutionResult]


@dataclass(frozen=True)
class DagRunResult:
    """Structured result for a complete or paused DAG run."""

    status: Literal["COMPLETE", "PAUSED"]
    passed: list[str]
    blocked: list[str]
    summary: str


class DagExecutionError(RuntimeError):
    """Raised when the DAG executor cannot proceed."""


class DagExecutor:
    """Walk DAG.yml in topological order, parallelize independent layers."""

    def __init__(
        self,
        dag_path: Path,
        completed_path: Path,
        root: Path,
        *,
        task_runner: TaskRunner | None = None,
    ) -> None:
        self._dag_path = dag_path
        self._completed_path = completed_path
        self._root = root
        self._run_id = str(uuid4())
        self._dag: dict[str, Any] = _load_yaml(dag_path)
        self._task_runner: TaskRunner = (
            task_runner if task_runner is not None else execute_task
        )

    def run(self) -> DagRunResult:
        """Execute all pending tasks in topological order."""
        return self._execute(self._load_completed())

    def resume(self) -> DagRunResult:
        """Re-enter after BLOCKED resolution; skips PASSED tasks."""
        return self._execute(self._load_completed())

    def _compute_ready_set(self, passed: set[str]) -> list[list[str]]:
        """Return ordered layers of ready tasks using Kahn's algorithm."""
        tasks = self._dag_tasks()
        task_ids: set[str] = {str(t["id"]) for t in tasks}
        deps: dict[str, set[str]] = {
            str(t["id"]): {str(d) for d in (t.get("depends_on") or [])}
            for t in tasks
        }
        pending_ids = task_ids - passed
        # Only consider deps that are themselves still pending (not already passed)
        remaining: dict[str, set[str]] = {
            tid: {d for d in deps[tid] if d in pending_ids}
            for tid in pending_ids
        }
        layers: list[list[str]] = []
        resolved: set[str] = set()
        while remaining:
            ready = sorted(tid for tid, d in remaining.items() if not d)
            if not ready:
                break  # cycle or unresolvable dependency
            layers.append(ready)
            resolved.update(ready)
            for tid in ready:
                del remaining[tid]
            for tid in remaining:
                remaining[tid] -= resolved
        return layers

    def _has_filescope_collision(self, task_a: str, task_b: str) -> bool:
        """Return True if the two tasks share any files in their filescope."""
        return bool(self._get_filescope(task_a) & self._get_filescope(task_b))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute(self, initial_passed: set[str]) -> DagRunResult:
        passed: set[str] = set(initial_passed)
        blocked: list[str] = []

        layers = self._compute_ready_set(passed)
        total = sum(len(layer) for layer in layers)
        self._emit(
            "dag_run_started", {"total_tasks": total, "layer_count": len(layers)}
        )

        for layer_index, layer in enumerate(layers):
            pending = [t for t in layer if t not in passed]
            if not pending:
                continue

            self._emit(
                "dag_layer_started",
                {"layer_index": layer_index, "task_ids": pending},
            )

            layer_blocked: list[str] = []
            groups = self._build_execution_groups(pending)

            for group in groups:
                results = self._run_group(group)
                for task_id, result in results.items():
                    if result.status == "PASS":
                        passed.add(task_id)
                    else:
                        layer_blocked.append(task_id)
                        blocked.append(task_id)
                        blocker_path = (
                            self._root
                            / "docs"
                            / "reports"
                            / f"{task_id}_blocker_report.md"
                        )
                        self._emit(
                            "dag_task_blocked",
                            {
                                "task_id": task_id,
                                "blocker_report_path": str(blocker_path),
                            },
                        )
                        print(f"[aiw run] BLOCKED: {task_id}")

                if layer_blocked:
                    # Don't start subsequent groups in this layer
                    break

            if layer_blocked:
                self._emit("dag_run_paused", {"blocked_task_id": layer_blocked[0]})
                return DagRunResult(
                    status="PAUSED",
                    passed=sorted(passed),
                    blocked=blocked,
                    summary=f"Paused after {len(blocked)} blocked task(s).",
                )

        summary = f"Complete: {len(passed)} task(s) passed."
        self._emit(
            "dag_run_complete", {"passed_count": len(passed), "summary": summary}
        )
        return DagRunResult(
            status="COMPLETE",
            passed=sorted(passed),
            blocked=[],
            summary=summary,
        )

    def _build_execution_groups(self, pending: list[str]) -> list[list[str]]:
        """Partition tasks: one concurrent group + serial singletons for colliders."""
        concurrent: list[str] = []
        serial: list[str] = []
        for task_id in pending:
            if any(self._has_filescope_collision(task_id, e) for e in concurrent):
                serial.append(task_id)
            else:
                concurrent.append(task_id)
        groups: list[list[str]] = []
        if concurrent:
            groups.append(concurrent)
        for task_id in serial:
            groups.append([task_id])
        return groups

    def _run_group(self, group: list[str]) -> dict[str, ExecutionResult]:
        """Execute a group of tasks, concurrently if more than one."""
        if len(group) == 1:
            return {group[0]: self._task_runner(group[0], self._root)}
        results: dict[str, ExecutionResult] = {}
        with ThreadPoolExecutor(max_workers=len(group)) as pool:
            futures = {
                pool.submit(self._task_runner, task_id, self._root): task_id
                for task_id in group
            }
            for future in as_completed(futures):
                task_id = futures[future]
                results[task_id] = future.result()
        return results

    def _get_filescope(self, task_id: str) -> set[str]:
        for task in self._dag_tasks():
            if str(task.get("id")) == task_id:
                scope = task.get("filescope") or []
                return {str(s) for s in scope} if isinstance(scope, list) else set()
        return set()

    def _dag_tasks(self) -> list[dict[str, Any]]:
        raw = self._dag.get("tasks", [])
        if not isinstance(raw, list):
            return []
        return cast(list[dict[str, Any]], raw)

    def _load_completed(self) -> set[str]:
        if not self._completed_path.exists():
            return set()
        passed: set[str] = set()
        for line in self._completed_path.read_text(encoding="utf-8").splitlines():
            parts = line.split("|")
            if len(parts) >= 2:
                task_id = parts[1].strip()
                if task_id.startswith("TASK-"):
                    passed.add(task_id)
        return passed

    def _emit(self, event_type: str, payload: dict[str, object]) -> None:
        """Write a DAG trace event as JSONL to the run-specific trace file."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "run_id": self._run_id,
            "payload": payload,
        }
        trace_path = self._root / ".aiw" / "runs" / f"dag-{self._run_id}.jsonl"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True) + "\n")


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise DagExecutionError(f"DAG file must contain a YAML mapping: {path}")
    return cast(dict[str, Any], data)


def run_dag(root: Path, resume: bool = False) -> DagRunResult:
    """Top-level entry called by CLI. Enforces PLANNED state before running."""
    constraints = load_constraints(root / "docs" / "constraints.yml")
    state_path = root / constraints.workflow.state_file
    machine = WorkflowStateMachine.load(state_path)
    if machine.current_state != "PLANNED":
        raise DagExecutionError(
            f"aiw run requires PLANNED state, found {machine.current_state}"
        )
    dag_path = root / "docs" / "tasks" / "DAG.yml"
    completed_path = root / "docs" / "tasks" / "COMPLETED.md"
    executor = DagExecutor(dag_path, completed_path, root)
    return executor.resume() if resume else executor.run()
