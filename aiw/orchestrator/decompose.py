"""Decompose command orchestration and atomic task artifact writes."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from aiw.infra import ConstraintsConfig, load_constraints
from aiw.workflow import IllegalStateTransitionError, WorkflowStateMachine
from aiw.workflow.gates import check_constraints_gate

RawDecomposeOutput = dict[str, str]


@dataclass(frozen=True)
class DecomposeResult:
    """Result metadata for a successful decompose run."""

    root: Path
    state: str
    command: str
    written_files: tuple[str, ...]


class DecomposeOutputError(RuntimeError):
    """Raised when the decompose session returns unusable output."""


def invoke_decompose_session(root: Path) -> RawDecomposeOutput:
    """Invoke the bounded decompose session.

    TASK-026 extends this stub with the actual AI-backed implementation.
    """
    raise NotImplementedError("decompose session invocation is implemented in TASK-026")


def run_decompose(root: Path) -> DecomposeResult:
    """Run `aiw decompose` with state validation, gate checks, and atomic writes."""
    config = load_constraints(root / "docs" / "constraints.yml")
    state_path = root / config.workflow.state_file
    current_state = _read_current_state(state_path)
    _ensure_command_allowed(config, current_state, "aiw decompose")
    check_constraints_gate(config)

    output = invoke_decompose_session(root)
    written_files = _write_outputs_atomically(root, output)

    machine = WorkflowStateMachine(current_state=current_state)
    next_state = machine.transition("aiw decompose")
    _write_current_state(state_path, next_state)

    return DecomposeResult(
        root=root,
        state=next_state,
        command="aiw decompose",
        written_files=tuple(sorted(written_files)),
    )


def _ensure_command_allowed(
    config: ConstraintsConfig, current_state: str, command: str
) -> None:
    allowed_commands = config.workflow.allowed_commands_by_state.get(current_state, [])
    if command not in allowed_commands:
        raise IllegalStateTransitionError(
            f"Illegal transition from {current_state!r} with {command!r}"
        )


def _write_outputs_atomically(root: Path, output: RawDecomposeOutput) -> list[str]:
    if not output:
        raise DecomposeOutputError("decompose session returned no task artifacts")

    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix="decompose-", dir=docs_dir))
    staged_tasks_dir = staging_root / "tasks"

    try:
        written_files = _stage_output_tree(staged_tasks_dir, output)
        _swap_tasks_tree(root / "docs" / "tasks", staged_tasks_dir)
    finally:
        if staging_root.exists():
            shutil.rmtree(staging_root, ignore_errors=True)

    return written_files


def _stage_output_tree(tasks_dir: Path, output: RawDecomposeOutput) -> list[str]:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    written_files: list[str] = []

    for relative_path, content in sorted(output.items()):
        normalized = _normalize_output_path(relative_path)
        destination = tasks_dir / normalized
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        written_files.append(f"docs/tasks/{normalized}")

    return written_files


def _swap_tasks_tree(target_dir: Path, staged_tasks_dir: Path) -> None:
    backup_dir = target_dir.with_name(f"{target_dir.name}.bak")
    if backup_dir.exists():
        shutil.rmtree(backup_dir)

    if target_dir.exists():
        target_dir.replace(backup_dir)

    try:
        staged_tasks_dir.replace(target_dir)
    except Exception:
        if backup_dir.exists() and not target_dir.exists():
            backup_dir.replace(target_dir)
        raise
    else:
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)


def _normalize_output_path(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        raise DecomposeOutputError(
            f"decompose output path must be relative: {relative_path!r}"
        )

    parts = path.parts
    if not parts:
        raise DecomposeOutputError("decompose output path must not be empty")
    if any(part in {"", ".", ".."} for part in parts):
        raise DecomposeOutputError(
            f"decompose output path escapes tasks directory: {relative_path!r}"
        )

    return path


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


def _write_current_state(state_path: Path, state: str) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"current_state": state, "state": state}
    state_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
