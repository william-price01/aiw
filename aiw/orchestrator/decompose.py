"""Decompose command orchestration and atomic task artifact writes."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from aiw.infra import ConstraintsConfig, load_constraints
from aiw.orchestrator.decompose_validator import validate_decompose_output
from aiw.workflow import IllegalStateTransitionError, WorkflowStateMachine
from aiw.workflow.gates import check_constraints_gate

RawDecomposeOutput = dict[str, str]
DecomposeSessionRunner = Callable[["PcpPaths", str], RawDecomposeOutput]


@dataclass(frozen=True)
class DecomposeResult:
    """Result metadata for a successful decompose run."""

    root: Path
    state: str
    command: str
    written_files: tuple[str, ...]


class DecomposeOutputError(RuntimeError):
    """Raised when the decompose session returns unusable output."""


class PcpPaths(dict[str, Path]):
    """Mapping of authoritative PCP artifact paths for the decompose session."""

    def __init__(self, root: Path, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.root = root

    def as_posix(self) -> str:
        """Compatibility shim for existing single-argument test doubles."""
        return self.root.as_posix()


_DECOMPOSE_SYSTEM_PROMPT = (
    "Generate deterministic planning artifacts for AIW decompose. "
    "Return a mapping of relative docs/tasks paths to full file contents. "
    "The output must include DAG.md, DAG.yml, and at least one TASK-###.md file."
)


def invoke_decompose_session(pcp_paths: PcpPaths) -> RawDecomposeOutput:
    """Invoke one bounded decompose session with PCP context."""
    prompt = _build_decompose_prompt(pcp_paths)
    return _run_bounded_decompose_ai_session(pcp_paths, prompt)


def run_decompose(root: Path) -> DecomposeResult:
    """Run `aiw decompose` with state validation, gate checks, and atomic writes."""
    config = load_constraints(root / "docs" / "constraints.yml")
    state_path = root / config.workflow.state_file
    current_state = WorkflowStateMachine.load(state_path).current_state
    _ensure_command_allowed(config, current_state, "aiw decompose")
    check_constraints_gate(config)

    output = invoke_decompose_session(_build_pcp_paths(root))
    validation_errors = validate_decompose_output(output)
    if validation_errors:
        raise DecomposeOutputError(
            "invalid decompose output: " + "; ".join(validation_errors)
        )
    written_files = _write_outputs_atomically(root, output)

    machine = WorkflowStateMachine(current_state=current_state)
    next_state = machine.transition("aiw decompose")
    machine.save(state_path)

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


def _build_pcp_paths(root: Path) -> PcpPaths:
    docs_root = root / "docs"
    pcp_paths = PcpPaths(
        root,
        {
            "docs/prd.md": docs_root / "prd.md",
            "docs/sdd.md": docs_root / "sdd.md",
            "docs/constraints.yml": docs_root / "constraints.yml",
        },
    )

    for adr_path in sorted((docs_root / "adrs").rglob("*")):
        if adr_path.is_file():
            pcp_paths[adr_path.relative_to(root).as_posix()] = adr_path

    return pcp_paths


def _build_decompose_prompt(pcp_paths: PcpPaths) -> str:
    sections = [_DECOMPOSE_SYSTEM_PROMPT]
    for relative_path, path in sorted(pcp_paths.items()):
        sections.append(f"\n[{relative_path}]")
        sections.append(path.read_text(encoding="utf-8"))
    return "\n".join(sections)


def _run_bounded_decompose_ai_session(
    pcp_paths: PcpPaths,
    prompt: str,
) -> RawDecomposeOutput:
    json_prompt = (
        f"{prompt}\n\n"
        "Return only valid JSON mapping relative docs/tasks paths to full "
        "file contents. "
        "Do not include markdown fences, explanations, or any surrounding text."
    )
    try:
        completed = subprocess.run(
            ("codex", "exec", json_prompt),
            check=True,
            capture_output=True,
            text=True,
            cwd=pcp_paths.root,
        )
    except subprocess.CalledProcessError as exc:
        detail = _excerpt_text(exc.stderr) or _excerpt_text(exc.stdout)
        suffix = f": {detail}" if detail else ""
        raise DecomposeOutputError(f"Codex CLI invocation failed{suffix}") from exc
    except FileNotFoundError as exc:
        raise DecomposeOutputError(
            "Codex CLI not found; ensure 'codex' is installed and on PATH"
        ) from exc

    stdout = completed.stdout.strip()
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        excerpt = _excerpt_text(stdout)
        suffix = f": {excerpt}" if excerpt else ""
        raise DecomposeOutputError(
            f"decompose session returned invalid JSON{suffix}"
        ) from exc

    if not isinstance(payload, dict) or not all(
        isinstance(path, str) and isinstance(content, str)
        for path, content in payload.items()
    ):
        raise DecomposeOutputError(
            "decompose session returned invalid JSON: expected object[str, str]"
        )

    return payload


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


def _excerpt_text(raw: str, limit: int = 500) -> str:
    text = raw.strip()
    if len(text) <= limit:
        return text
    return text[:limit]
