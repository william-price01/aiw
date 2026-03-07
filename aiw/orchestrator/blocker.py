"""Blocker report generation for exhausted AIW task runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class BlockerContext:
    """Inputs required to generate exhaustion-related reports."""

    root: Path
    iterations_used: int
    last_test_output: str
    failure_reason: str
    followup_tasks: tuple[str, ...] = field(default_factory=tuple)
    scope_expansion_request: str | None = None


def generate_blocker_report(task_id: str, context: BlockerContext) -> Path:
    """Write the required blocker report under ``docs/reports``."""
    report_path = _report_path(context.root, task_id, "blocker_report")
    lines = [
        f"# {task_id} blocker report",
        "",
        f"- Task ID: {task_id}",
        f"- Iterations used: {context.iterations_used}",
        f"- Failure reason: {context.failure_reason}",
        "",
        "## Last test output",
        "```text",
        _normalized_output(context.last_test_output),
        "```",
        "",
    ]
    return _write_report(report_path, "\n".join(lines))


def generate_followup_tasks(task_id: str, context: BlockerContext) -> Path | None:
    """Write follow-up task suggestions when the exhausted task should be split."""
    if not context.followup_tasks:
        return None

    report_path = _report_path(context.root, task_id, "followup_tasks")
    items = [f"{index}. {task}" for index, task in enumerate(context.followup_tasks, 1)]
    body = "\n".join(
        [
            f"# {task_id} follow-up tasks",
            "",
            (
                f"Generated because `{task_id}` exhausted "
                f"{context.iterations_used} iterations."
            ),
            "",
            *items,
            "",
        ]
    )
    return _write_report(report_path, body)


def generate_scope_expansion_request(
    task_id: str,
    context: BlockerContext,
) -> Path | None:
    """Write a scope-expansion request when the correct fix exceeds task scope."""
    if context.scope_expansion_request is None:
        return None

    report_path = _report_path(context.root, task_id, "scope_expansion_request")
    body = "\n".join(
        [
            f"# {task_id} scope expansion request",
            "",
            f"- Task ID: {task_id}",
            f"- Iterations used: {context.iterations_used}",
            f"- Reason: {context.scope_expansion_request}",
            "",
        ]
    )
    return _write_report(report_path, body)


def _report_path(root: Path, task_id: str, suffix: str) -> Path:
    return root / "docs" / "reports" / f"{task_id}_{suffix}.md"


def _normalized_output(output: str) -> str:
    normalized = output.strip()
    return normalized if normalized else "[no test output captured]"


def _write_report(path: Path, contents: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    return path
