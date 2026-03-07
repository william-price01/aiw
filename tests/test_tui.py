from __future__ import annotations

import json
from pathlib import Path

from aiw.cli.tui import render_run_trace, render_status, render_task_list


def test_render_status_reads_persisted_workflow_state(tmp_path: Path) -> None:
    state_path = tmp_path / ".aiw" / "workflow_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "current_state": "PLANNED",
                "metadata": {"run_id": "run-123"},
                "state": "PLANNED",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    rendered = render_status(tmp_path)

    assert rendered == "\n".join(
        [
            "Workflow Status",
            "State: PLANNED",
            "Run ID: run-123",
            "Source: .aiw/workflow_state.json",
        ]
    )


def test_render_status_omits_run_id_when_metadata_is_missing(tmp_path: Path) -> None:
    state_path = tmp_path / ".aiw" / "workflow_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps({"current_state": "PLANNED", "state": "PLANNED"}, indent=2) + "\n",
        encoding="utf-8",
    )

    rendered = render_status(tmp_path)

    assert rendered == "\n".join(
        [
            "Workflow Status",
            "State: PLANNED",
            "Source: .aiw/workflow_state.json",
        ]
    )


def test_render_task_list_derives_statuses_from_task_artifacts(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "docs" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "TASK-001.md").write_text("task 1\n", encoding="utf-8")
    (tasks_dir / "TASK-002.md").write_text("task 2\n", encoding="utf-8")
    (tasks_dir / "TASK-003.md").write_text("task 3\n", encoding="utf-8")
    (tasks_dir / "TASK-002.log.md").write_text(
        "\n".join(
            [
                "## Run `run-old`",
                "",
                "- Termination: `PASS`",
                "",
                "## Run `run-new`",
                "",
                "- Termination: `BLOCKED`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tasks_dir / "COMPLETED.md").write_text(
        "\n".join(
            [
                "# Completed Tasks",
                "",
                "| Task ID | Run ID | Completed At (UTC) | Result | Notes |",
                "|---|---|---|---|---|",
                (
                    "| TASK-001 | run-1 | 2026-03-07T00:00:00Z |"
                    " PASS | Completed by aiw go |"
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rendered = render_task_list(tmp_path)

    assert rendered == "\n".join(
        [
            "Task List",
            "TASK-001: PASS (COMPLETED.md)",
            "TASK-002: BLOCKED (TASK-002.log.md)",
            "TASK-003: NOT_RUN (TASK-003.md only)",
        ]
    )


def test_render_run_trace_formats_jsonl_events(tmp_path: Path) -> None:
    run_path = tmp_path / ".aiw" / "runs" / "run-20260307T120000Z.jsonl"
    run_path.parent.mkdir(parents=True)
    run_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-03-07T12:00:00Z",
                        "event_type": "state_transition",
                        "run_id": "run-123",
                        "payload": {
                            "from_state": "PLANNED",
                            "to_state": "EXECUTING",
                        },
                    },
                    sort_keys=True,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-07T12:00:01Z",
                        "event_type": "run_complete",
                        "run_id": "run-123",
                        "payload": {"status": "PASS", "task_id": "TASK-024"},
                    },
                    sort_keys=True,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rendered = render_run_trace(run_path)

    assert rendered == "\n".join(
        [
            "Run Trace",
            f"Source: {run_path}",
            (
                "1. 2026-03-07T12:00:00Z state_transition "
                '{"from_state": "PLANNED", "to_state": "EXECUTING"}'
            ),
            (
                "2. 2026-03-07T12:00:01Z run_complete "
                '{"status": "PASS", "task_id": "TASK-024"}'
            ),
        ]
    )


def test_renderers_do_not_modify_input_files(tmp_path: Path) -> None:
    state_path = tmp_path / ".aiw" / "workflow_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"state": "BLOCKED"}) + "\n", encoding="utf-8")

    tasks_dir = tmp_path / "docs" / "tasks"
    tasks_dir.mkdir(parents=True)
    task_path = tasks_dir / "TASK-024.md"
    task_path.write_text("task body\n", encoding="utf-8")
    completed_path = tasks_dir / "COMPLETED.md"
    completed_path.write_text("", encoding="utf-8")

    run_path = tmp_path / ".aiw" / "runs" / "run-20260307T120000Z.jsonl"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-03-07T12:00:00Z",
                "event_type": "blocked",
                "payload": {"task_id": "TASK-024"},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    before = {
        state_path: state_path.read_text(encoding="utf-8"),
        task_path: task_path.read_text(encoding="utf-8"),
        completed_path: completed_path.read_text(encoding="utf-8"),
        run_path: run_path.read_text(encoding="utf-8"),
    }

    render_status(tmp_path)
    render_task_list(tmp_path)
    render_run_trace(run_path)

    after = {path: path.read_text(encoding="utf-8") for path in before}
    assert after == before
