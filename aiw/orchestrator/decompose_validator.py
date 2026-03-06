"""Validation for AI-generated decompose task artifacts."""

from __future__ import annotations

import re
from collections.abc import Mapping

import yaml

RawDecomposeOutput = dict[str, str]

_TASK_FILE_PATTERN = re.compile(r"^TASK-\d{3}\.md$")
_DAG_TASK_REQUIRED_KEYS = (
    "id",
    "title",
    "type",
    "depends_on",
    "filescope",
    "tests",
    "acceptance",
)
_TASK_TEMPLATE_FIELDS = {
    "Type:": "Type",
    "Depends_on:": "Depends_on",
    "Objective:": "Objective",
    "File scope allowlist:": "File scope allowlist",
    "Non-goals:": "Non-goals",
    "Acceptance criteria (measurable):": "Acceptance criteria",
    "Tests / checks required:": "Tests / checks required",
}


def validate_decompose_output(output: RawDecomposeOutput) -> list[str]:
    """Return validation errors for generated decompose artifacts."""
    errors: list[str] = []

    dag_markdown = output.get("DAG.md")
    if dag_markdown is None:
        errors.append("Missing DAG.md")
    elif not dag_markdown.strip():
        errors.append("DAG.md must be non-empty")

    dag_yaml = output.get("DAG.yml")
    if dag_yaml is None:
        errors.append("Missing DAG.yml")
    else:
        errors.extend(_validate_dag_yaml(dag_yaml))

    task_files = sorted(
        relative_path
        for relative_path in output
        if _TASK_FILE_PATTERN.fullmatch(relative_path) is not None
    )
    if not task_files:
        errors.append("Missing TASK-###.md files")
    else:
        for task_file in task_files:
            errors.extend(_validate_task_file(task_file, output[task_file]))

    return errors


def _validate_dag_yaml(raw_yaml: str) -> list[str]:
    try:
        loaded = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        return [f"Invalid DAG.yml YAML: {exc}"]

    if not isinstance(loaded, dict):
        return ["DAG.yml must deserialize to a mapping"]

    tasks = loaded.get("tasks")
    if not isinstance(tasks, list):
        return ["DAG.yml must contain a top-level 'tasks' list"]

    errors: list[str] = []
    for index, task_entry in enumerate(tasks):
        if not isinstance(task_entry, Mapping):
            errors.append(f"DAG.yml tasks[{index}] must be a mapping")
            continue
        for key in _DAG_TASK_REQUIRED_KEYS:
            if key not in task_entry:
                errors.append(f"DAG.yml tasks[{index}] missing required key: {key}")

    return errors


def _validate_task_file(relative_path: str, content: str) -> list[str]:
    if not content.strip():
        return [f"{relative_path} must be non-empty"]

    if not _looks_like_task_template(content):
        return []

    errors: list[str] = []
    for marker, field_name in _TASK_TEMPLATE_FIELDS.items():
        if not _field_has_content(content, marker):
            errors.append(f"{relative_path} missing required field: {field_name}")
    return errors


def _field_has_content(content: str, marker: str) -> bool:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(marker):
            inline_value = line[len(marker) :].strip()
            if inline_value:
                return True

            for trailing_line in lines[index + 1 :]:
                if _is_section_header(trailing_line):
                    return False
                if trailing_line.strip():
                    return True
            return False
    return False


def _is_section_header(line: str) -> bool:
    if not line.strip():
        return False
    if line.startswith("## "):
        return True
    return line.endswith(":") and not line.startswith(("- ", "* ", "  "))


def _looks_like_task_template(content: str) -> bool:
    stripped = content.lstrip()
    if stripped.startswith("## TASK-"):
        return True
    return any(marker in content for marker in _TASK_TEMPLATE_FIELDS)
