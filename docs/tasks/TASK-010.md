## TASK-010: Observability — JSONL trace emitter

Type: IMPLEMENTATION
Depends_on: [TASK-002]

Objective:
Implement a structured JSONL trace emitter that writes required trace events to `.aiw/runs/run-<timestamp>.jsonl`.

Context (spec refs):
- PRD §7.6 (observability)
- SDD §5.2 (EXECUTING entry semantics — run_id)
- constraints.yml: `observability.traces.required_events`, `observability.artifacts.jsonl_trace_path`

Inputs:
- Run ID (generated at EXECUTING entry)
- Event type and payload

Outputs (artifacts/files created or changed):
- `aiw/infra/trace.py`
- `tests/test_trace.py`

File scope allowlist:
- aiw/infra/trace.py
- tests/test_trace.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `TraceEmitter` class with:
  - `__init__(run_id: str, output_path: Path)`
  - `emit(event_type: str, payload: dict) -> None`
- Each line is valid JSON with: `timestamp`, `event_type`, `run_id`, `payload`.
- Append-only within a run.

Constraints enforced:
- `observability.traces.required_events` (all 14 event types supported)
- `observability.artifacts.jsonl_trace_path`

Non-goals:
- No event-generating logic (callers emit events).

Acceptance criteria (measurable):
- Writes valid JSONL to `.aiw/runs/run-<timestamp>.jsonl`.
- All 14 required event types can be emitted.
- Each line parses as valid JSON.
- Each event has `timestamp`, `event_type`, `run_id`.
- File is append-only.

Tests / checks required:
- `pytest tests/test_trace.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Self-referential: this IS the observability layer.

Rollback plan:
- `git checkout` to pre-task baseline.
