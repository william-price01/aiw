"""Task preflight linting helpers."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path

from aiw.infra import ConstraintsConfig

_TASK_SECTION_MARKERS: dict[str, str] = {
    "Depends_on:": "Depends_on",
    "Objective:": "Objective",
    "Acceptance criteria (measurable):": "Acceptance criteria",
    "Tests / checks required:": "Tests / checks required",
    "File scope allowlist:": "File scope allowlist",
    "Non-goals:": "Non-goals",
}


@dataclass(frozen=True)
class TaskLintFailedEvent:
    """Structured trace event payload for task lint failures."""

    event_type: str
    payload: dict[str, object]


class TaskLintError(RuntimeError):
    """Raised when a task file fails preflight lint validation."""

    errors: tuple[str, ...]
    event: TaskLintFailedEvent

    def __init__(self, task_path: Path, errors: list[str]) -> None:
        self.errors = tuple(errors)
        self.event = TaskLintFailedEvent(
            event_type="task_lint_failed",
            payload={
                "task_path": task_path.as_posix(),
                "errors": list(self.errors),
            },
        )
        super().__init__("Task lint failed: " + "; ".join(self.errors))


def lint_task(task_path: Path, constraints: ConstraintsConfig) -> list[str]:
    """Return lint errors for a task file before execution is allowed."""
    errors: list[str] = []
    task_name = task_path.name
    expected_pattern = constraints.agents.task_scoped_coding_agent.task_id_regex

    if not task_path.is_file():
        return [f"Task file does not exist: {task_path.as_posix()}"]

    if task_path.suffix != ".md":
        errors.append(f"Task file must be a markdown file: {task_name}")

    if re.fullmatch(expected_pattern, task_path.stem) is None:
        errors.append(
            "Task file name does not match configured task id regex: "
            f"{task_name} ({expected_pattern})"
        )

    content = task_path.read_text(encoding="utf-8")
    for marker, field_name in _TASK_SECTION_MARKERS.items():
        if not _field_has_content(content, marker):
            errors.append(f"Missing required field: {field_name}")

    file_scope_entries = _extract_section_entries(content, "File scope allowlist:")
    if file_scope_entries:
        errors.extend(_validate_file_scope(file_scope_entries, constraints))

    return errors


def check_task_lint(task_path: Path, constraints: ConstraintsConfig) -> None:
    """Raise a structured error when a task file fails lint validation."""
    errors = lint_task(task_path, constraints)
    if errors:
        raise TaskLintError(task_path, errors)


def _validate_file_scope(
    file_scope_entries: list[str],
    constraints: ConstraintsConfig,
) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()

    for entry in file_scope_entries:
        normalized_path = entry.strip().replace("\\", "/")
        if not normalized_path or normalized_path in seen:
            continue
        seen.add(normalized_path)

        if _matches_any(
            normalized_path, constraints.write_scope_validation.forbid_paths
        ):
            errors.append(f"Forbidden file scope path: {normalized_path}")
            continue

        if not _matches_any(
            normalized_path, constraints.write_scope_validation.allowed_edit_paths
        ):
            errors.append(
                "File scope path is outside global allowed edit paths: "
                f"{normalized_path}"
            )

    return errors


def _extract_section_entries(content: str, marker: str) -> list[str]:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(marker):
            entries: list[str] = []
            inline_value = line[len(marker) :].strip()
            if inline_value:
                entries.append(inline_value)

            for trailing_line in lines[index + 1 :]:
                if _is_section_header(trailing_line):
                    break

                stripped = trailing_line.strip()
                if not stripped:
                    continue
                if stripped.startswith(("- ", "* ")):
                    entries.append(stripped[2:].strip())
                else:
                    entries.append(stripped)

            return entries

    return []


def _field_has_content(content: str, marker: str) -> bool:
    return bool(_extract_section_entries(content, marker))


def _is_section_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if line.startswith("## "):
        return True
    return stripped.endswith(":") and not stripped.startswith(("- ", "* "))


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)
