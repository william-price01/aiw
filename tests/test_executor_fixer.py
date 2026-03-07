"""Tests for the executor failure path with Fixer and exhaustion handling."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import cast

from aiw.orchestrator.coder import DiffStats, PatchResult, TaskSpec
from aiw.orchestrator.executor import execute_task


def test_execute_task_spawns_fixer_and_returns_to_planned(tmp_path: Path) -> None:
    repo_root = _init_repo(tmp_path)
    fixer_calls: list[str] = []

    def coder_runner(task_spec: TaskSpec, constraints: object) -> PatchResult:
        del task_spec, constraints
        return _patch_result(
            "aiw/example.py",
            "VALUE = 1\n",
            "VALUE = 0\n",
        )

    def fixer_runner(
        task_spec: TaskSpec,
        test_output: str,
        constraints: object,
    ) -> PatchResult:
        del task_spec, constraints
        fixer_calls.append(test_output)
        return _patch_result(
            "aiw/example.py",
            "VALUE = 0\n",
            "VALUE = 2\n",
        )

    result = execute_task(
        "TASK-027",
        repo_root,
        coder_runner=coder_runner,
        fixer_runner=fixer_runner,
    )

    assert result.status == "PASS"
    assert result.iterations_used == 2
    assert len(fixer_calls) == 1
    assert "1 failed" in fixer_calls[0]
    assert _state_payload(repo_root)["current_state"] == "PLANNED"
    assert _state_payload(repo_root)["run_id"] == result.run_id
    assert (repo_root / "aiw" / "example.py").read_text(encoding="utf-8") == (
        "VALUE = 2\n"
    )

    event_types = _trace_event_types(repo_root)
    assert "test_run_failed" in event_types
    assert "fixer_spawned" in event_types
    assert event_types.count("fixer_spawned") == 1
    assert event_types[-1] == "run_complete"


def test_execute_task_blocks_after_failed_fixer_with_iteration_exhaustion(
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    fixer_calls: list[str] = []

    def coder_runner(task_spec: TaskSpec, constraints: object) -> PatchResult:
        del task_spec, constraints
        return _patch_result(
            "aiw/example.py",
            "VALUE = 1\n",
            "VALUE = 0\n",
        )

    def fixer_runner(
        task_spec: TaskSpec,
        test_output: str,
        constraints: object,
    ) -> PatchResult:
        del task_spec, constraints
        fixer_calls.append(test_output)
        return _patch_result(
            "aiw/example.py",
            "VALUE = 0\n",
            "VALUE = 3\n",
        )

    result = execute_task(
        "TASK-027",
        repo_root,
        coder_runner=coder_runner,
        fixer_runner=fixer_runner,
    )

    assert result.status == "BLOCKED"
    assert result.iterations_used == 3
    assert len(fixer_calls) == 1
    assert _state_payload(repo_root)["current_state"] == "BLOCKED"

    event_types = _trace_event_types(repo_root)
    assert event_types.count("fixer_spawned") == 1
    assert "iteration_exhausted" in event_types
    assert "blocked" in event_types
    assert event_types[-1] == "run_complete"


def _init_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    subprocess.run(
        ("git", "init"),
        check=True,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ("git", "config", "user.name", "AIW Tests"),
        check=True,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ("git", "config", "user.email", "aiw-tests@example.com"),
        check=True,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    (repo_root / "docs" / "constraints.yml").parent.mkdir(parents=True, exist_ok=True)
    (repo_root / "docs" / "constraints.yml").write_text(
        Path("docs/constraints.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (repo_root / "docs" / "tasks").mkdir(parents=True, exist_ok=True)
    (repo_root / "docs" / "tasks" / "TASK-027.md").write_text(
        """## TASK-027: Executor fixer path

Depends_on:
- TASK-015

Objective:
- Exercise the failure path.

Acceptance criteria (measurable):
- Failure spawns fixer.

Tests / checks required:
- pytest tests/test_example.py -q

File scope allowlist:
- aiw/example.py
- tests/test_example.py

Non-goals:
- None.
""",
        encoding="utf-8",
    )
    (repo_root / "docs" / "tasks" / "COMPLETED.md").write_text(
        "# Completed\n",
        encoding="utf-8",
    )

    (repo_root / "aiw").mkdir()
    (repo_root / "aiw" / "__init__.py").write_text("", encoding="utf-8")
    (repo_root / "aiw" / "example.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo_root / "tests").mkdir()
    (repo_root / "tests" / "test_example.py").write_text(
        "from aiw.example import VALUE\n\n\n"
        "def test_value() -> None:\n"
        "    assert VALUE == 2\n",
        encoding="utf-8",
    )

    (repo_root / ".aiw").mkdir()
    (repo_root / ".aiw" / "workflow_state.json").write_text(
        json.dumps({"current_state": "PLANNED"}, indent=2) + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        ("git", "add", "."),
        check=True,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ("git", "commit", "-m", "seed"),
        check=True,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    return repo_root


def _patch_result(path: str, before: str, after: str) -> PatchResult:
    patch = (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1 +1 @@\n"
        f"-{before.rstrip()}\n"
        f"+{after.rstrip()}\n"
    )
    return PatchResult(
        changed_files=(path,),
        diff_stats=DiffStats(files_changed=1, lines_changed=2),
        success=True,
        patch=patch,
    )


def _state_payload(repo_root: Path) -> dict[str, str]:
    return cast(
        dict[str, str],
        json.loads(
            (repo_root / ".aiw" / "workflow_state.json").read_text(encoding="utf-8")
        ),
    )


def _trace_event_types(repo_root: Path) -> list[str]:
    run_files = sorted((repo_root / ".aiw" / "runs").glob("*.jsonl"))
    assert run_files
    return [
        json.loads(line)["event_type"]
        for line in run_files[0].read_text(encoding="utf-8").splitlines()
    ]
