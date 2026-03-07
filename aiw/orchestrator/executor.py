"""Bounded task execution loop for AIW task runs."""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator
from uuid import uuid4

from aiw.infra import ConstraintsConfig, load_constraints
from aiw.infra.checkpoint import create_checkpoint
from aiw.infra.trace import TraceEmitter
from aiw.orchestrator.blocker import BlockerContext, generate_blocker_report
from aiw.orchestrator.coder import PatchResult, TaskSpec, run_coder_session
from aiw.orchestrator.fixer import build_fixer_spawned_event_data, run_fixer_session
from aiw.tasks.lint import check_task_lint
from aiw.workflow import WorkflowStateMachine
from aiw.workflow.gates import check_constraints_gate
from aiw.workflow.locking import LockViolationError, check_lock_violations

PatchRunner = Callable[[TaskSpec, ConstraintsConfig], PatchResult]
FixerRunner = Callable[[TaskSpec, str, ConstraintsConfig], PatchResult]
PatchApplier = Callable[[str, Path], None]


@dataclass(frozen=True)
class ExecutionResult:
    """Structured terminal result for a bounded task execution run."""

    status: str
    iterations_used: int
    run_id: str


@dataclass(frozen=True)
class TestRunResult:
    """Captured output for a deterministic local test run."""

    passed: bool
    output: str
    exit_code: int


class ExecutionError(RuntimeError):
    """Raised when execution cannot start or complete deterministically."""


def execute_task(
    task_id: str,
    root: Path,
    *,
    coder_runner: PatchRunner | None = None,
    fixer_runner: FixerRunner | None = None,
    patch_applier: PatchApplier | None = None,
) -> ExecutionResult:
    """Execute one task through the bounded Coder/Fixer loop."""
    repo_root = root.resolve()
    constraints = load_constraints(repo_root / "docs" / "constraints.yml")
    check_constraints_gate(constraints)

    task_path = repo_root / "docs" / "tasks" / f"{task_id}.md"
    check_task_lint(task_path, constraints)
    task_spec = TaskSpec.from_file(task_path)

    state_path = repo_root / constraints.workflow.state_file
    machine = WorkflowStateMachine.load(state_path)

    if machine.current_state != "PLANNED":
        raise ExecutionError(
            f"task execution requires PLANNED state, found {machine.current_state}"
        )

    run_id = str(uuid4())
    trace = TraceEmitter(run_id, _trace_path(repo_root, constraints))
    trace.emit("constraint_validation", {"task_id": task_id, "status": "passed"})

    _transition(
        machine,
        state_path,
        trace,
        "aiw go TASK-###",
        run_id=run_id,
        write_run_id=constraints.execution.run_id.write_on_enter_executing,
    )

    with _pushd(repo_root):
        create_checkpoint(f"{task_id} baseline")

    run_coder = coder_runner or _default_coder_runner(repo_root)
    run_fixer = fixer_runner or _default_fixer_runner(repo_root)
    apply_patch = patch_applier or _apply_patch

    coder_patch = run_coder(task_spec, constraints)
    _emit_patch_validation_events(trace, task_id, "coder", coder_patch)
    apply_patch(coder_patch.patch, repo_root)

    initial_test = _run_tests(repo_root, constraints, trace, task_id, 1)
    if initial_test.passed:
        return _finalize_pass(
            machine=machine,
            state_path=state_path,
            trace=trace,
            constraints=constraints,
            task_id=task_id,
            run_id=run_id,
            iterations_used=1,
            repo_root=repo_root,
        )

    trace.emit(
        "test_run_failed",
        {"task_id": task_id, "iteration": 1, "exit_code": initial_test.exit_code},
    )
    trace.emit(
        "quality_gate_failed",
        {
            "task_id": task_id,
            "gate": "tests",
            "iteration": 1,
            "exit_code": initial_test.exit_code,
        },
    )
    trace.emit(
        "fixer_spawned",
        build_fixer_spawned_event_data(task_spec, initial_test.output, constraints),
    )

    fixer_patch = run_fixer(task_spec, initial_test.output, constraints)
    _emit_patch_validation_events(trace, task_id, "fixer", fixer_patch)
    apply_patch(fixer_patch.patch, repo_root)

    fixed_test = _run_tests(repo_root, constraints, trace, task_id, 2)
    if fixed_test.passed:
        return _finalize_pass(
            machine=machine,
            state_path=state_path,
            trace=trace,
            constraints=constraints,
            task_id=task_id,
            run_id=run_id,
            iterations_used=2,
            repo_root=repo_root,
        )

    trace.emit(
        "test_run_failed",
        {"task_id": task_id, "iteration": 2, "exit_code": fixed_test.exit_code},
    )
    trace.emit(
        "quality_gate_failed",
        {
            "task_id": task_id,
            "gate": "tests",
            "iteration": 2,
            "exit_code": fixed_test.exit_code,
        },
    )
    trace.emit(
        "iteration_exhausted",
        {
            "task_id": task_id,
            "iterations_used": constraints.execution.max_iterations_per_task,
            "max_iterations_per_task": constraints.execution.max_iterations_per_task,
        },
    )
    _transition(machine, state_path, trace, "on:exhaustion", run_id=run_id)
    blocker_context = BlockerContext(
        root=repo_root,
        iterations_used=constraints.execution.max_iterations_per_task,
        last_test_output=fixed_test.output,
        failure_reason="iteration_exhausted",
    )
    generate_blocker_report(task_id, blocker_context)
    trace.emit(
        "blocked",
        {
            "task_id": task_id,
            "reason": "iteration_exhausted",
            "iterations_used": constraints.execution.max_iterations_per_task,
        },
    )
    trace.emit(
        "run_complete",
        {
            "task_id": task_id,
            "status": "BLOCKED",
            "iterations_used": constraints.execution.max_iterations_per_task,
        },
    )
    return ExecutionResult(
        status="BLOCKED",
        iterations_used=constraints.execution.max_iterations_per_task,
        run_id=run_id,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _default_coder_runner(repo_root: Path) -> PatchRunner:
    return lambda task_spec, constraints: run_coder_session(
        task_spec, constraints, repo_root=repo_root
    )


def _default_fixer_runner(repo_root: Path) -> FixerRunner:
    return lambda task_spec, test_output, constraints: run_fixer_session(
        task_spec, test_output, constraints, repo_root=repo_root
    )


def _emit_patch_validation_events(
    trace: TraceEmitter,
    task_id: str,
    phase: str,
    patch_result: PatchResult,
) -> None:
    violations = check_lock_violations("EXECUTING", list(patch_result.changed_files))
    if violations:
        error = LockViolationError(violations)
        trace.emit(
            "lock_violation_hard_fail",
            {
                "task_id": task_id,
                "phase": phase,
                "violations": list(error.violations),
            },
        )
        raise ExecutionError(str(error))

    trace.emit(
        "scope_validation",
        {
            "task_id": task_id,
            "phase": phase,
            "changed_files": list(patch_result.changed_files),
            "status": "passed",
        },
    )
    trace.emit(
        "diff_threshold_check",
        {
            "task_id": task_id,
            "phase": phase,
            "files_changed": patch_result.diff_stats.files_changed,
            "lines_changed": patch_result.diff_stats.lines_changed,
            "status": "passed",
        },
    )


def _run_tests(
    repo_root: Path,
    constraints: ConstraintsConfig,
    trace: TraceEmitter,
    task_id: str,
    iteration: int,
) -> TestRunResult:
    command = _parse_command(constraints.quality.test_command)
    _clear_python_caches(repo_root)

    env = os.environ.copy()
    repo_path = str(repo_root)
    current_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        repo_path if not current_pythonpath
        else f"{repo_path}{os.pathsep}{current_pythonpath}"
    )

    trace.emit(
        "test_run_started",
        {"task_id": task_id, "iteration": iteration, "command": command},
    )

    completed = subprocess.run(
        tuple(command),
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    output = completed.stdout
    if completed.stderr:
        output = f"{output}\n{completed.stderr}" if output else completed.stderr

    if completed.returncode == 0:
        trace.emit(
            "test_run_passed",
            {
                "task_id": task_id,
                "iteration": iteration,
                "exit_code": completed.returncode,
            },
        )

    return TestRunResult(
        passed=completed.returncode == 0,
        output=output,
        exit_code=completed.returncode,
    )


def _clear_python_caches(repo_root: Path) -> None:
    for cache_dir in repo_root.rglob("__pycache__"):
        if cache_dir.is_dir():
            shutil.rmtree(cache_dir)


def _finalize_pass(
    *,
    machine: WorkflowStateMachine,
    state_path: Path,
    trace: TraceEmitter,
    constraints: ConstraintsConfig,
    task_id: str,
    run_id: str,
    iterations_used: int,
    repo_root: Path,
) -> ExecutionResult:
    if constraints.execution.task_completion.enabled:
        _append_task_completion(constraints, repo_root, task_id, run_id)
        trace.emit(
            "task_marked_complete",
            {
                "task_id": task_id,
                "run_id": run_id,
                "tracker_file": constraints.execution.task_completion.tracker_file,
            },
        )
    _transition(machine, state_path, trace, "on:success", run_id=run_id)
    trace.emit(
        "run_complete",
        {"task_id": task_id, "status": "PASS", "iterations_used": iterations_used},
    )
    return ExecutionResult(
        status="PASS",
        iterations_used=iterations_used,
        run_id=run_id,
    )


def _append_task_completion(
    constraints: ConstraintsConfig,
    repo_root: Path,
    task_id: str,
    run_id: str,
) -> None:
    task_completion = constraints.execution.task_completion
    if not task_completion.mark_on_pass:
        return
    tracker_path = repo_root / task_completion.tracker_file
    tracker_path.parent.mkdir(parents=True, exist_ok=True)
    completed_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    line = f"| {task_id} | {run_id} | {completed_at} | PASS | Completed by aiw go |\n"
    with tracker_path.open("a", encoding="utf-8") as f:
        f.write(line)


def _transition(
    machine: WorkflowStateMachine,
    state_path: Path,
    trace: TraceEmitter,
    command: str,
    *,
    run_id: str,
    write_run_id: bool = False,
) -> None:
    from_state = machine.current_state
    to_state = machine.transition(command)
    _save_workflow_state(state_path, to_state, run_id if write_run_id else None)
    trace.emit(
        "state_transition",
        {"from_state": from_state, "to_state": to_state, "trigger": command},
    )


def _save_workflow_state(
    state_path: Path,
    current_state: str,
    run_id: str | None,
) -> None:
    payload: dict[str, str] = {}
    if state_path.exists():
        existing_payload = json.loads(state_path.read_text(encoding="utf-8"))
        if isinstance(existing_payload, dict):
            payload = {
                key: value
                for key, value in existing_payload.items()
                if isinstance(key, str) and isinstance(value, str)
            }

    payload["current_state"] = current_state
    if run_id is not None:
        payload["run_id"] = run_id

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _trace_path(repo_root: Path, constraints: ConstraintsConfig) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    template = constraints.observability.artifacts.jsonl_trace_path
    return repo_root / template.replace("<timestamp>", timestamp)


def _parse_command(command: str | None) -> list[str]:
    if command is None:
        raise ExecutionError("quality.test_command must be configured")
    normalized = command.strip().strip("`").strip()
    if not normalized:
        raise ExecutionError("quality.test_command must be a non-empty command")
    return shlex.split(normalized)


def _apply_patch(patch: str, repo_root: Path) -> None:
    completed = subprocess.run(
        ("git", "apply", "--whitespace=nowarn", "-"),
        input=patch,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        suffix = f": {detail}" if detail else ""
        raise ExecutionError(f"git apply failed{suffix}")


@contextmanager
def _pushd(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(previous)
