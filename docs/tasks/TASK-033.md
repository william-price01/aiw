## TASK-033: Extend WorkflowStateMachine to carry and persist optional metadata

Type: IMPLEMENTATION
Depends_on: [TASK-002, TASK-030, TASK-031, TASK-032]

Objective:
Extend `WorkflowStateMachine` to carry an optional `metadata` dict that is
persisted alongside `current_state` in `.aiw/workflow_state.json`. Remove the
executor workaround where `run_id` is written by a separate code path. Ensure
`recovery.py` and `tui.py` continue to read `run_id` correctly without changes
to their read logic.

Context (spec refs):
- PRD §7.4 (execution artifacts — workflow state is authoritative)
- SDD §5.2 (EXECUTING entry semantics — run_id written on enter EXECUTING)
- constraints.yml: `execution.run_id.write_on_enter_EXECUTING`

Problem being fixed:
`WorkflowStateMachine.save()` only writes `current_state`. The executor
generates a `run_id` on EXECUTING entry and passes it to `_transition()`, which
calls `machine.save()` — but `run_id` is never written to the state file.
`recovery.py` (line 48) and `tui.py` (line 32) both read `run_id` from the raw
state payload, so they silently receive `None` on every run. The executor's
`_transition()` also accepts `run_id` as a parameter that it currently does not
use beyond passing to the trace emitter.

Inputs:
- `aiw/workflow/state_machine.py` (TASK-002)
- `aiw/orchestrator/executor.py` (TASK-030, TASK-031, TASK-032)
- `tests/test_state_machine.py`
- `tests/test_executor_happy.py`

Outputs (artifacts/files created or changed):
- `aiw/workflow/state_machine.py`
- `aiw/orchestrator/executor.py`
- `tests/test_state_machine.py`
- `tests/test_executor_happy.py`

File scope allowlist:
- aiw/workflow/state_machine.py
- aiw/orchestrator/executor.py
- tests/test_state_machine.py
- tests/test_executor_happy.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

---

## Required changes

### 1. `aiw/workflow/state_machine.py`

**Add `metadata` field to `WorkflowStateMachine`:**

```python
def __init__(
    self,
    current_state: str = "INIT",
    metadata: dict[str, object] | None = None,
) -> None:
    ...
    self._metadata: dict[str, object] = dict(metadata) if metadata else {}
```

**Add `set_metadata` and `get_metadata` accessors:**

```python
def set_metadata(self, key: str, value: object) -> None:
    """Set a metadata key on the state machine (persisted on next save)."""
    self._metadata[key] = value

def get_metadata(self, key: str, default: object = None) -> object:
    """Retrieve a metadata value by key."""
    return self._metadata.get(key, default)
```

**Update `load()` to deserialize metadata:**

```python
@classmethod
def load(cls, path: Path) -> WorkflowStateMachine:
    if not path.exists():
        return cls()
    data = json.loads(path.read_text(encoding="utf-8"))
    current_state = data.get("current_state")
    if not isinstance(current_state, str):
        raise ValueError("workflow state file missing string field 'current_state'")
    raw_metadata = data.get("metadata")
    metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
    return cls(current_state=current_state, metadata=metadata)
```

**Update `save()` to serialize metadata:**

```python
def save(self, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"current_state": self._current_state}
    if self._metadata:
        payload["metadata"] = dict(self._metadata)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
```

**Key invariant:** When `_metadata` is empty, `save()` must omit the `metadata`
key entirely so the state file format stays minimal for non-execution states.
Tests must verify this.

---

### 2. `aiw/orchestrator/executor.py`

**In `_transition()`**: after `machine.transition(command)`, if `run_id` is
provided, call `machine.set_metadata("run_id", run_id)` before `machine.save()`.
This replaces any separate state-file write that currently exists for `run_id`.

```python
def _transition(
    machine: WorkflowStateMachine,
    state_path: Path,
    trace: TraceEmitter,
    command: str,
    *,
    run_id: str,
) -> None:
    from_state = machine.current_state
    to_state = machine.transition(command)
    machine.set_metadata("run_id", run_id)
    machine.save(state_path)
    trace.emit(
        "state_transition",
        {"from_state": from_state, "to_state": to_state, "trigger": command},
    )
```

**Remove any separate state-file write for `run_id`** that was added as a
workaround in TASK-030 or earlier. A single `machine.save()` in `_transition()`
is the only write.

**Do not change** `_finalize_pass()`, `_finalize_blocked()`, or any other
executor logic beyond `_transition()`. The `run_id` parameter signature of
`_transition()` stays as-is.

---

### 3. `tests/test_state_machine.py`

Add tests covering:

- `set_metadata` / `get_metadata` round-trips in memory.
- `save()` with non-empty metadata includes `"metadata"` key in JSON.
- `save()` with empty metadata omits `"metadata"` key from JSON.
- `load()` deserializes metadata correctly.
- `load()` on a file without `"metadata"` key returns empty metadata (backward
  compatibility with existing state files).
- `load()` on a file where `"metadata"` is not a dict raises `ValueError` or
  silently falls back to empty dict — choose one behavior and test it. Prefer
  silent fallback to empty dict (more resilient to manual edits).

---

### 4. `tests/test_executor_happy.py`

Add or update one test asserting that after `execute_task()` returns with
`status == "PASS"`, the state file at `.aiw/workflow_state.json` contains
`run_id` under `metadata`, and the value matches `result.run_id`.

```python
state = json.loads((repo_root / ".aiw" / "workflow_state.json").read_text())
assert state.get("metadata", {}).get("run_id") == result.run_id
```

If a test already asserts `state["run_id"] == result.run_id` (flat key), update
it to the nested form above.

---

## Constraints enforced

- `execution.run_id.required`: true
- `execution.run_id.write_on_enter_EXECUTING`: true
- `workflow.state_file`: `.aiw/workflow_state.json`

## Non-goals

- Do not change `recovery.py` or `tui.py`. They read `run_id` from the raw
  JSON payload directly (not through `WorkflowStateMachine`). After this task,
  `payload["metadata"]["run_id"]` will exist in the file, so their existing
  reads — which look at the top-level key — will still return `None` unless
  updated. That is a separate follow-up (TASK-034, if needed) and is explicitly
  out of scope here.
- Do not add metadata fields beyond `run_id`.
- Do not change the `_transition()` function signature.
- Do not touch any other test files beyond the two in the allowlist.
- Do not change the trace emitter or JSONL format.

## Acceptance criteria (measurable)

- `WorkflowStateMachine(metadata={"run_id": "abc"}).get_metadata("run_id")` returns `"abc"`.
- `save()` with non-empty metadata writes `{"current_state": ..., "metadata": {...}}`.
- `save()` with empty metadata writes `{"current_state": ...}` only (no `"metadata"` key).
- `load()` on a file with `"metadata": {"run_id": "abc"}` returns machine where `get_metadata("run_id") == "abc"`.
- `load()` on a file without `"metadata"` key returns machine where `get_metadata("run_id") is None`.
- After `execute_task()` PASS: `workflow_state.json` contains `metadata.run_id == result.run_id`.
- No separate state-file write for `run_id` exists outside `machine.save()`.
- `pytest tests/test_state_machine.py -q` passes.
- `pytest tests/test_executor_happy.py -q` passes.
- `ruff check .` passes.
- `mypy aiw tests` passes.

## Tests / checks required

- `pytest tests/test_state_machine.py -q`
- `pytest tests/test_executor_happy.py -q`
- `ruff check .`
- `mypy aiw tests`

## Observability requirements

- No new trace events. The `run_id` in the state file is not an observability
  artifact — it is persistence for crash recovery and TUI display. The trace
  emitter already receives `run_id` directly.

## Rollback plan

- `git checkout` to pre-task baseline.
