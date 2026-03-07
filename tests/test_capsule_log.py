"""Tests for append-only markdown capsule logs."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from aiw.orchestrator.executor import ExecutionResult
from aiw.tasks.capsule_log import write_capsule_log


def test_write_capsule_log_writes_required_markdown_sections(tmp_path: Path) -> None:
    _write_constraints(
        tmp_path,
        "agents:\n  task_scoped_coding_agent:\n    memory: {}\n",
    )
    result = _result(
        status="PASS",
        iterations_used=2,
        run_id="run-123",
        diff_summaries=[
            "Iteration 1: updated aiw/tasks/capsule_log.py",
            {"iteration": 2, "summary": "tightened markdown rendering"},
        ],
        test_results=[
            {"iteration": 1, "summary": "pytest failed with exit_code=1"},
            "Iteration 2: pytest passed",
        ],
        failures_encountered=["Iteration 1: failing pytest"],
        patch_rationale=["Keep the writer append-only and human-readable."],
        status_transitions=["EXECUTING -> PLANNED"],
    )

    log_path = write_capsule_log("TASK-020", result, tmp_path)

    expected_hash = sha256(
        (tmp_path / "docs" / "constraints.yml").read_bytes()
    ).hexdigest()
    assert log_path == tmp_path / "docs" / "tasks" / "TASK-020.log.md"

    content = log_path.read_text(encoding="utf-8")
    assert content.startswith("## Run `run-123`")
    assert "- Chosen task: `TASK-020`" in content
    assert f"- Constraints hash: `{expected_hash}`" in content
    assert "- Termination: `PASS`" in content
    assert "### Diff Summaries" in content
    assert "Iteration 1: updated aiw/tasks/capsule_log.py" in content
    assert "Iteration 2: tightened markdown rendering" in content
    assert "### Test Results" in content
    assert "Iteration 1: pytest failed with exit_code=1" in content
    assert "Iteration 2: pytest passed" in content
    assert "### Failures Encountered" in content
    assert "### Patch Rationale" in content
    assert "### Status Transitions" in content


def test_write_capsule_log_appends_multiple_runs(tmp_path: Path) -> None:
    _write_constraints(tmp_path, "quality:\n  test_command: pytest -q\n")
    first = _result(
        status="BLOCKED",
        iterations_used=3,
        run_id="run-1",
        constraints_hash="hash-1",
        diff_summaries=["Iteration 1: initial patch"],
        test_results=["Iteration 1: pytest failed"],
    )
    second = _result(
        status="PASS",
        iterations_used=1,
        run_id="run-2",
        constraints_hash="hash-2",
        diff_summaries=["Iteration 1: follow-up patch"],
        test_results=["Iteration 1: pytest passed"],
    )

    log_path = write_capsule_log("TASK-020", first, tmp_path)
    write_capsule_log("TASK-020", second, tmp_path)

    content = log_path.read_text(encoding="utf-8")
    assert content.count("## Run `") == 2
    assert content.index("## Run `run-1`") < content.index("## Run `run-2`")
    assert "- Constraints hash: `hash-1`" in content
    assert "- Constraints hash: `hash-2`" in content
    assert "- Termination: `BLOCKED`" in content
    assert "- Termination: `PASS`" in content


def _write_constraints(tmp_path: Path, content: str) -> None:
    constraints_path = tmp_path / "docs" / "constraints.yml"
    constraints_path.parent.mkdir(parents=True, exist_ok=True)
    constraints_path.write_text(content, encoding="utf-8")


def _result(
    *,
    status: str,
    iterations_used: int,
    run_id: str,
    constraints_hash: str | None = None,
    diff_summaries: list[object] | None = None,
    test_results: list[object] | None = None,
    failures_encountered: list[str] | None = None,
    patch_rationale: list[str] | None = None,
    status_transitions: list[str] | None = None,
) -> ExecutionResult:
    result = ExecutionResult(
        status=status,
        iterations_used=iterations_used,
        run_id=run_id,
    )
    extras = {
        "diff_summaries": diff_summaries or [],
        "test_results": test_results or [],
        "failures_encountered": failures_encountered or [],
        "patch_rationale": patch_rationale or [],
        "status_transitions": status_transitions or [],
    }
    if constraints_hash is not None:
        extras["constraints_hash"] = constraints_hash

    for name, value in extras.items():
        object.__setattr__(result, name, value)
    return result
