"""Write-scope and diff-size validation helpers."""

from __future__ import annotations

import fnmatch

from aiw.infra import ConstraintsConfig


def validate_scope(
    changed_files: list[str],
    task_allowlist: list[str],
    constraints: ConstraintsConfig,
) -> list[str]:
    """Return scope violations for the proposed set of changed files."""
    if not constraints.write_scope_validation.enabled:
        return []

    violations: list[str] = []
    seen: set[str] = set()

    for changed_file in changed_files:
        normalized_path = _normalize_path(changed_file)
        if not normalized_path or normalized_path in seen:
            continue
        seen.add(normalized_path)

        if _matches_any(
            normalized_path, constraints.write_scope_validation.forbid_paths
        ):
            violations.append(f"forbidden_path:{normalized_path}")
            continue

        if not _matches_any(
            normalized_path, constraints.write_scope_validation.allowed_edit_paths
        ):
            violations.append(f"outside_global_allowlist:{normalized_path}")
            continue

        if not _matches_any(normalized_path, task_allowlist):
            violations.append(f"outside_task_allowlist:{normalized_path}")

    return violations


def validate_diff_size(
    files_changed: int,
    lines_changed: int,
    constraints: ConstraintsConfig,
) -> list[str]:
    """Return diff-threshold violations for proposed change size."""
    if not constraints.diff_validation.enabled:
        return []

    violations: list[str] = []
    diff_validation = constraints.diff_validation

    if files_changed > diff_validation.max_files_changed:
        violations.append(
            "max_files_changed_exceeded:"
            f"{files_changed}>{diff_validation.max_files_changed}"
        )

    if lines_changed > diff_validation.max_lines_changed:
        violations.append(
            "max_lines_changed_exceeded:"
            f"{lines_changed}>{diff_validation.max_lines_changed}"
        )

    return violations


def _normalize_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)
