"""Happy-path task execution orchestration."""

from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from aiw.infra import ConstraintsConfig, load_constraints
from aiw.infra.checkpoint import create_checkpoint
from aiw.infra.trace import TraceEmitter
from aiw.orchestrator.coder import (
    CodexRunner,
    PatchResult,
    TaskSpec,
    run_coder_session,
)
from aiw.tasks.lint import check_task_lint
from aiw.workflow import IllegalStateTransitionError, WorkflowStateMachine
from aiw.workflow.gates import check_constraints_gate


@dataclass(frozen=True)
class ExecutionResult:
    """Result metadata for a successful happy-path execution run."""

    status: str
    iterations_used: int
    run_id: str


def execute_task(
    task_id: str,
    root: Path,
    *,
    codex_runner: CodexRunner | None = None,
) -> ExecutionResult:
    """Execute one task through the happy path and return PASS metadata."""
    normalized_root = root.resolve()
    config = load_constraints(normalized_root / "docs" / "constraints.yml")
    state_path = normalized_root / config.workflow.state_file
    current_state = _read_current_state(state_path)
    _ensure_command_allowed(config, current_state, "aiw go TASK-###")

    task_path = normalized_root / "docs" / "tasks" / f"{task_id}.md"
    check_constraints_gate(config)
    check_task_lint(task_path, config)

    run_id = str(uuid4())
    trace = TraceEmitter(run_id, _build_trace_path(normalized_root, config))
    trace.emit("constraint_validation", {"task_id": task_id, "result": "passed"})

    checkpoint_ref = create_checkpoint(f"{task_id} baseline")

    machine = WorkflowStateMachine(current_state=current_state)
    next_state = machine.transition("aiw go TASK-###")
    _write_state(state_path, next_state, run_id=run_id)
    trace.emit(
        "state_transition",
        {
            "task_id": task_id,
            "from_state": current_state,
            "to_state": next_state,
            "command": "aiw go TASK-###",
            "checkpoint_ref": checkpoint_ref,
        },
    )

    task_spec = TaskSpec.from_file(task_path)
    patch_result = run_coder_session(
        task_spec,
        config,
        repo_root=normalized_root,
        codex_runner=codex_runner,
    )
    trace.emit(
        "scope_validation",
        {
            "task_id": task_id,
            "changed_files": list(patch_result.changed_files),
            "result": "passed",
        },
    )
    trace.emit(
        "diff_threshold_check",
        {
            "task_id": task_id,
            "files_changed": patch_result.diff_stats.files_changed,
            "lines_changed": patch_result.diff_stats.lines_changed,
            "result": "passed",
        },
    )

    _apply_patch(normalized_root, patch_result)

    normalized_test_command = _normalize_shell_command(config.quality.test_command)
    trace.emit(
        "test_run_started",
        {"task_id": task_id, "command": normalized_test_command},
    )
    _run_test_command(normalized_root, config)
    trace.emit(
        "test_run_passed",
        {"task_id": task_id, "command": normalized_test_command},
    )

    completed_at = _utc_now_iso()
    _append_completion_record(
        normalized_root / config.execution.task_completion.tracker_file,
        task_id=task_id,
        run_id=run_id,
        completed_at=completed_at,
    )
    trace.emit(
        "task_marked_complete",
        {
            "task_id": task_id,
            "run_id": run_id,
            "completed_at": completed_at,
            "result": "PASS",
        },
    )

    final_state = machine.transition("on:success")
    _write_state(state_path, final_state, run_id=run_id)
    trace.emit(
        "state_transition",
        {
            "task_id": task_id,
            "from_state": next_state,
            "to_state": final_state,
            "command": "on:success",
        },
    )
    trace.emit(
        "run_complete",
        {
            "task_id": task_id,
            "status": "PASS",
            "iterations_used": 1,
        },
    )

    return ExecutionResult(status="PASS", iterations_used=1, run_id=run_id)


def _ensure_command_allowed(
    config: ConstraintsConfig, current_state: str, command: str
) -> None:
    allowed_commands = config.workflow.allowed_commands_by_state.get(current_state, [])
    if command not in allowed_commands:
        raise IllegalStateTransitionError(
            f"Illegal transition from {current_state!r} with {command!r}"
        )


def _read_current_state(state_path: Path) -> str:
    if not state_path.exists():
        return "INIT"

    data = json.loads(state_path.read_text(encoding="utf-8"))
    for key in ("current_state", "state"):
        value = data.get(key)
        if isinstance(value, str):
            return value

    raise ValueError(
        "workflow state file missing string field 'current_state' or 'state'"
    )


def _write_state(state_path: Path, state: str, *, run_id: str) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"current_state": state, "run_id": run_id, "state": state}
    state_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _build_trace_path(root: Path, config: ConstraintsConfig) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    template = config.observability.artifacts.jsonl_trace_path
    return root / template.replace("<timestamp>", timestamp)


def _apply_patch(root: Path, patch_result: PatchResult) -> None:
    if not patch_result.patch:
        return

    try:
        subprocess.run(
            ("git", "apply", "--whitespace=nowarn", "-"),
            check=True,
            capture_output=True,
            text=True,
            cwd=root,
            input=patch_result.patch,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        stdout = exc.stdout.strip()
        detail = stderr or stdout
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"git apply failed{suffix}") from exc


def _run_test_command(root: Path, config: ConstraintsConfig) -> None:
    command = _normalize_shell_command(config.quality.test_command)
    if command is None or not command.strip():
        raise ValueError("quality.test_command must be configured")

    try:
        subprocess.run(
            shlex.split(command),
            check=True,
            capture_output=True,
            text=True,
            cwd=root,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        stdout = exc.stdout.strip()
        detail = stderr or stdout
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"test command failed{suffix}") from exc


def _normalize_shell_command(command: str | None) -> str | None:
    if command is None:
        return None
    stripped = command.strip()
    if len(stripped) >= 2 and stripped.startswith("`") and stripped.endswith("`"):
        return stripped[1:-1].strip()
    return stripped


def _append_completion_record(
    completed_path: Path,
    *,
    task_id: str,
    run_id: str,
    completed_at: str,
) -> None:
    line = f"| {task_id} | {run_id} | {completed_at} | PASS | Completed by aiw go |\n"
    with completed_path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )
