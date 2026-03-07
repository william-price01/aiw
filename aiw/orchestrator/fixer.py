"""Bounded Fixer session integration for failed AIW task runs."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from aiw.infra import ConstraintsConfig
from aiw.orchestrator.coder import (
    CoderSessionError,
    CodexRunner,
    PatchResult,
    PatchValidationError,
    TaskSpec,
    _build_patch,
    _get_changed_files,
    _get_diff_stats,
    _invoke_codex_cli,
    _validate_task_spec,
)
from aiw.tasks.scope_validator import validate_diff_size, validate_scope

_FAILED_TEST_PATTERNS = (
    re.compile(r"(?mi)^FAILED\b"),
    re.compile(r"(?mi)^=+ FAILURES =+$"),
    re.compile(r"(?i)\b\d+\s+failed\b"),
    re.compile(r"(?i)\b\d+\s+error(?:s)?\b"),
    re.compile(r"(?m)^Traceback \(most recent call last\):$"),
)
_MAX_TEST_OUTPUT_CHARS = 4000


class FixerSessionError(CoderSessionError):
    """Raised when the bounded Fixer invocation cannot complete."""


def run_fixer_session(
    task_spec: TaskSpec,
    test_output: str,
    constraints: ConstraintsConfig,
    *,
    repo_root: Path | None = None,
    codex_runner: CodexRunner | None = None,
) -> PatchResult:
    """Run exactly one Fixer session after a failed test run."""
    _validate_task_spec(task_spec, constraints)
    _validate_test_failure_output(test_output)

    root = (repo_root or Path.cwd()).resolve()
    runner = codex_runner or _invoke_codex_cli

    with tempfile.TemporaryDirectory(
        prefix=f"{task_spec.task_id.lower()}-fixer-"
    ) as td:
        workspace = Path(td) / "workspace"
        shutil.copytree(root, workspace)

        prompt = _build_fixer_prompt(task_spec, test_output, constraints)
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


def build_fixer_spawned_event_data(
    task_spec: TaskSpec,
    test_output: str,
    constraints: ConstraintsConfig,
) -> dict[str, object]:
    """Return the structured payload for a ``fixer_spawned`` trace event."""
    _validate_test_failure_output(test_output)
    return {
        "task_id": task_spec.task_id,
        "trigger": "test_failed",
        "write_scope_allowlist": list(task_spec.file_scope_allowlist),
        "max_iterations_per_task": constraints.execution.max_iterations_per_task,
        "failed_test_output_excerpt": _truncate_test_output(test_output),
    }


def _build_fixer_prompt(
    task_spec: TaskSpec,
    test_output: str,
    constraints: ConstraintsConfig,
) -> str:
    allowlist = "\n".join(f"- {path}" for path in task_spec.file_scope_allowlist)
    return "\n".join(
        [
            "Repair exactly one failed AIW task in this workspace copy.",
            f"Task ID: {task_spec.task_id}",
            "Use a single bounded fixer pass.",
            "Spawn only because tests have already failed.",
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
            "Failed test output:",
            _truncate_test_output(test_output),
            "",
            f"[{task_spec.path.as_posix()}]",
            task_spec.content,
        ]
    )


def _validate_test_failure_output(test_output: str) -> None:
    normalized = test_output.strip()
    if not normalized:
        raise ValueError("fixer session requires failed test output")

    if any(pattern.search(normalized) for pattern in _FAILED_TEST_PATTERNS):
        return

    raise ValueError("fixer session may only spawn after a failed test run")


def _truncate_test_output(test_output: str) -> str:
    normalized = test_output.strip()
    if len(normalized) <= _MAX_TEST_OUTPUT_CHARS:
        return normalized
    return normalized[:_MAX_TEST_OUTPUT_CHARS].rstrip() + "\n...[truncated]"
