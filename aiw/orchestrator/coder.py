"""Bounded Coder session integration for task-scoped AIW execution."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from aiw.infra import ConstraintsConfig
from aiw.tasks.scope_validator import validate_diff_size, validate_scope

_TASK_HEADER_PATTERN = re.compile(r"^##\s+(TASK-\d{3})\b", re.MULTILINE)
_FILE_SCOPE_MARKER = "File scope allowlist:"

CodexRunner = Callable[[Path, str], None]


@dataclass(frozen=True)
class TaskSpec:
    """Task-scoped context passed into the bounded Coder session."""

    task_id: str
    path: Path
    content: str
    file_scope_allowlist: tuple[str, ...]

    @classmethod
    def from_file(cls, path: Path) -> TaskSpec:
        """Load a task spec and extract its task ID and file allowlist."""
        content = path.read_text(encoding="utf-8")
        task_id = _extract_task_id(content, path)
        allowlist = _extract_file_scope_allowlist(content, path)
        return cls(
            task_id=task_id,
            path=path,
            content=content,
            file_scope_allowlist=allowlist,
        )


@dataclass(frozen=True)
class DiffStats:
    """Normalized diff-size metadata for a proposed patch."""

    files_changed: int
    lines_changed: int


@dataclass(frozen=True)
class PatchResult:
    """Structured patch proposal returned by the Coder session."""

    changed_files: tuple[str, ...]
    diff_stats: DiffStats
    success: bool
    patch: str


class CoderSessionError(RuntimeError):
    """Raised when the bounded Codex invocation fails."""


class PatchValidationError(RuntimeError):
    """Raised when a proposed patch violates task or global constraints."""

    def __init__(
        self,
        *,
        scope_violations: list[str],
        diff_violations: list[str],
    ) -> None:
        self.scope_violations = tuple(scope_violations)
        self.diff_violations = tuple(diff_violations)

        parts: list[str] = []
        if scope_violations:
            parts.append("scope violations: " + ", ".join(scope_violations))
        if diff_violations:
            parts.append("diff violations: " + ", ".join(diff_violations))

        super().__init__("Invalid coder patch proposal: " + "; ".join(parts))


def run_coder_session(
    task_spec: TaskSpec,
    constraints: ConstraintsConfig,
    *,
    repo_root: Path | None = None,
    codex_runner: CodexRunner | None = None,
) -> PatchResult:
    """Run exactly one Codex CLI session and validate the proposed patch."""
    _validate_task_spec(task_spec, constraints)

    root = (repo_root or Path.cwd()).resolve()
    runner = codex_runner or _invoke_codex_cli

    with tempfile.TemporaryDirectory(
        prefix=f"{task_spec.task_id.lower()}-coder-"
    ) as td:
        workspace = Path(td) / "workspace"
        shutil.copytree(root, workspace)

        prompt = _build_coder_prompt(task_spec, constraints)
        runner(workspace, prompt)

        changed_files = _get_changed_files(workspace)
        diff_stats = _get_diff_stats(workspace, changed_files)
        patch = _build_patch(workspace, changed_files)

    scope_violations = validate_scope(
        changed_files=list(changed_files),
        task_allowlist=list(task_spec.file_scope_allowlist),
        constraints=constraints,
    )
    diff_violations = validate_diff_size(
        files_changed=diff_stats.files_changed,
        lines_changed=diff_stats.lines_changed,
        constraints=constraints,
    )
    if scope_violations or diff_violations:
        raise PatchValidationError(
            scope_violations=scope_violations,
            diff_violations=diff_violations,
        )

    return PatchResult(
        changed_files=changed_files,
        diff_stats=diff_stats,
        success=True,
        patch=patch,
    )


def _build_coder_prompt(task_spec: TaskSpec, constraints: ConstraintsConfig) -> str:
    allowlist = "\n".join(f"- {path}" for path in task_spec.file_scope_allowlist)
    return "\n".join(
        [
            "Implement exactly one AIW task in this workspace copy.",
            f"Task ID: {task_spec.task_id}",
            "Use a single bounded coding pass.",
            "Edit only files in this task-scoped allowlist:",
            allowlist,
            "",
            "Hard constraints:",
            "- Do not edit files outside the allowlist.",
            "- Do not edit any .aiw/** internal tool state paths.",
            (
                "- Cross-task edits are forbidden."
                if constraints.agents.task_scoped_coding_agent.no_cross_task_edits
                else "- Cross-task edit policy disabled."
            ),
            "",
            f"[{task_spec.path.as_posix()}]",
            task_spec.content,
        ]
    )


def _invoke_codex_cli(workspace: Path, prompt: str) -> None:
    try:
        subprocess.run(
            ("codex", "exec", prompt),
            check=True,
            capture_output=True,
            text=True,
            cwd=workspace,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        stdout = exc.stdout.strip()
        detail = stderr or stdout
        suffix = f": {detail}" if detail else ""
        raise CoderSessionError(f"Codex CLI invocation failed{suffix}") from exc
    except FileNotFoundError as exc:
        raise CoderSessionError(
            "Codex CLI invocation failed: executable not found"
        ) from exc


def _validate_task_spec(task_spec: TaskSpec, constraints: ConstraintsConfig) -> None:
    if (
        constraints.agents.task_scoped_coding_agent.enforced
        and not re.fullmatch(
            constraints.agents.task_scoped_coding_agent.task_id_regex,
            task_spec.task_id,
        )
    ):
        raise ValueError(f"invalid task id for coder session: {task_spec.task_id!r}")
    if not task_spec.file_scope_allowlist:
        raise ValueError("task spec file scope allowlist must be non-empty")


def _extract_task_id(content: str, path: Path) -> str:
    match = _TASK_HEADER_PATTERN.search(content)
    if match is not None:
        return match.group(1)

    filename = path.stem
    if re.fullmatch(r"TASK-\d{3}", filename):
        return filename

    raise ValueError(f"unable to determine task id from {path.as_posix()}")


def _extract_file_scope_allowlist(content: str, path: Path) -> tuple[str, ...]:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != _FILE_SCOPE_MARKER:
            continue

        allowlist: list[str] = []
        for candidate in lines[index + 1 :]:
            stripped = candidate.strip()
            if not stripped:
                if allowlist:
                    break
                continue
            if stripped.startswith("- "):
                allowlist.append(stripped[2:].strip())
                continue
            if allowlist:
                break
            raise ValueError(
                f"file scope allowlist in {path.as_posix()} must contain bullet items"
            )

        if allowlist:
            return tuple(allowlist)
        break

    raise ValueError(f"missing file scope allowlist in {path.as_posix()}")


def _get_changed_files(workspace: Path) -> tuple[str, ...]:
    completed = _run_git(
        workspace,
        "status",
        "--short",
        "--untracked-files=all",
    )
    changed_files: list[str] = []
    seen: set[str] = set()

    for raw_line in completed.stdout.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        path_fragment = line[3:] if len(line) > 3 else ""
        if " -> " in path_fragment:
            path_fragment = path_fragment.split(" -> ", maxsplit=1)[1]
        normalized = _normalize_path(path_fragment)
        if normalized and normalized not in seen:
            seen.add(normalized)
            changed_files.append(normalized)

    return tuple(changed_files)


def _get_diff_stats(workspace: Path, changed_files: Sequence[str]) -> DiffStats:
    total_lines_changed = 0
    tracked_files = _tracked_changed_files(workspace, changed_files)
    untracked_files = _untracked_changed_files(workspace, changed_files)

    if tracked_files:
        completed = _run_git(workspace, "diff", "--numstat", "--", *tracked_files)
        total_lines_changed += _sum_numstat_lines(completed.stdout)

    for relative_path in untracked_files:
        completed = _run_git(
            workspace,
            "diff",
            "--no-index",
            "--numstat",
            "--",
            "/dev/null",
            relative_path,
            check=False,
        )
        total_lines_changed += _sum_numstat_lines(completed.stdout)

    return DiffStats(
        files_changed=len(changed_files),
        lines_changed=total_lines_changed,
    )


def _build_patch(workspace: Path, changed_files: Sequence[str]) -> str:
    if not changed_files:
        return ""

    patch_chunks: list[str] = []
    tracked_files = _tracked_changed_files(workspace, changed_files)
    untracked_files = _untracked_changed_files(workspace, changed_files)

    if tracked_files:
        completed = _run_git(workspace, "diff", "--binary", "--", *tracked_files)
        if completed.stdout:
            patch_chunks.append(completed.stdout)

    for relative_path in untracked_files:
        completed = _run_git(
            workspace,
            "diff",
            "--no-index",
            "--binary",
            "--",
            "/dev/null",
            relative_path,
            check=False,
        )
        if completed.stdout:
            patch_chunks.append(completed.stdout)

    return "".join(patch_chunks)


def _tracked_changed_files(workspace: Path, changed_files: Sequence[str]) -> list[str]:
    tracked: list[str] = []
    for relative_path in changed_files:
        completed = _run_git(
            workspace,
            "ls-files",
            "--error-unmatch",
            "--",
            relative_path,
            check=False,
        )
        if completed.returncode == 0:
            tracked.append(relative_path)
    return tracked


def _untracked_changed_files(
    workspace: Path, changed_files: Sequence[str]
) -> list[str]:
    tracked = set(_tracked_changed_files(workspace, changed_files))
    return [
        relative_path for relative_path in changed_files if relative_path not in tracked
    ]


def _sum_numstat_lines(output: str) -> int:
    total = 0
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        additions, deletions = parts[0], parts[1]
        if additions.isdigit():
            total += int(additions)
        if deletions.isdigit():
            total += int(deletions)
    return total


def _normalize_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def _run_git(
    workspace: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ("git", *args),
            check=check,
            capture_output=True,
            text=True,
            cwd=workspace,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        stdout = exc.stdout.strip()
        detail = stderr or stdout
        suffix = f": {detail}" if detail else ""
        raise CoderSessionError(f"git {' '.join(args)} failed{suffix}") from exc
