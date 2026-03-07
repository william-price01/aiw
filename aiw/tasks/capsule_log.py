"""Append-only markdown capsule logs for task execution runs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any

from aiw.orchestrator.executor import ExecutionResult

_PATH_TEMPLATE = Path("docs/tasks/{TASK_ID}.log.md")


def write_capsule_log(
    task_id: str,
    run_result: ExecutionResult,
    output_dir: Path,
) -> Path:
    """Append one markdown capsule entry for a task execution run."""
    log_path = output_dir / str(_PATH_TEMPLATE).format(TASK_ID=task_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    entry = _render_entry(task_id, run_result, output_dir)
    prefix = ""
    if log_path.exists() and log_path.read_text(encoding="utf-8").strip():
        prefix = "\n\n"

    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{prefix}{entry}\n")

    return log_path


def _render_entry(task_id: str, run_result: ExecutionResult, output_dir: Path) -> str:
    chosen_task = getattr(run_result, "chosen_task", task_id)
    constraints_hash = _resolve_constraints_hash(run_result, output_dir)
    diff_summaries = _normalize_entries(getattr(run_result, "diff_summaries", ()))
    test_results = _normalize_entries(getattr(run_result, "test_results", ()))
    failures = _normalize_entries(getattr(run_result, "failures_encountered", ()))
    rationale = _normalize_entries(getattr(run_result, "patch_rationale", ()))
    transitions = _normalize_entries(getattr(run_result, "status_transitions", ()))

    lines = [
        f"## Run `{run_result.run_id}`",
        "",
        f"- Chosen task: `{chosen_task}`",
        f"- Constraints hash: `{constraints_hash}`",
        f"- Iterations used: `{run_result.iterations_used}`",
        f"- Termination: `{run_result.status}`",
        "",
        "### Diff Summaries",
        *_markdown_list(diff_summaries, empty_label="No diff summaries recorded."),
        "",
        "### Test Results",
        *_markdown_list(test_results, empty_label="No test results recorded."),
        "",
        "### Failures Encountered",
        *_markdown_list(failures, empty_label="None."),
        "",
        "### Patch Rationale",
        *_markdown_list(rationale, empty_label="Not recorded."),
        "",
        "### Status Transitions",
        *_markdown_list(
            transitions or [f"Run completed with `{run_result.status}`."],
            empty_label="Not recorded.",
        ),
    ]
    return "\n".join(lines)


def _resolve_constraints_hash(run_result: ExecutionResult, output_dir: Path) -> str:
    explicit_hash = getattr(run_result, "constraints_hash", None)
    if isinstance(explicit_hash, str) and explicit_hash.strip():
        return explicit_hash.strip()

    constraints_path = output_dir / "docs" / "constraints.yml"
    if constraints_path.exists():
        return sha256(constraints_path.read_bytes()).hexdigest()
    return "unavailable"


def _normalize_entries(raw_entries: Any) -> list[str]:
    if raw_entries is None:
        return []
    if isinstance(raw_entries, str):
        return [raw_entries]
    if isinstance(raw_entries, Mapping):
        return [_stringify_mapping(raw_entries)]
    if isinstance(raw_entries, Iterable):
        normalized: list[str] = []
        for item in raw_entries:
            if isinstance(item, str):
                normalized.append(item)
            elif isinstance(item, Mapping):
                normalized.append(_stringify_mapping(item))
            else:
                normalized.append(str(item))
        return normalized
    return [str(raw_entries)]


def _stringify_mapping(entry: Mapping[str, Any]) -> str:
    if "summary" in entry:
        summary = str(entry["summary"])
        iteration = entry.get("iteration")
        if iteration is not None:
            return f"Iteration {iteration}: {summary}"
        return summary

    parts = [f"{key}={entry[key]}" for key in sorted(entry)]
    return ", ".join(parts)


def _markdown_list(entries: list[str], *, empty_label: str) -> list[str]:
    if not entries:
        return [f"- {empty_label}"]
    return [f"- {entry}" for entry in entries]
