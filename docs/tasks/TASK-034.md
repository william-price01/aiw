## TASK-034: Update recovery.py and tui.py to read run_id from metadata

Type: IMPLEMENTATION
Depends_on: [TASK-033]

Objective:
Update `recovery.py` and `tui.py` to read `run_id` from
`payload["metadata"]["run_id"]` instead of the flat top-level key
`payload["run_id"]`. Update their test files to write state fixtures using the
nested form and assert against nested reads.

Context (spec refs):
- SDD §5.2 (EXECUTING entry semantics — run_id written on enter EXECUTING)
- SDD §5.3 (crash / stale EXECUTING determinism — recovery reads run_id from
  state file)
- PRD §15 (TUI derives strictly from workflow state)

Problem being fixed:
TASK-033 moved `run_id` persistence from a flat top-level key to
`metadata.run_id` in `.aiw/workflow_state.json`. Two files still read the old
flat location and receive `None` on every run:

- `aiw/workflow/recovery.py` line 48:
  `run_id = str(payload.get("run_id") or "stale-execution-recovery")`
- `aiw/cli/tui.py` line 32:
  `run_id = _string_field(payload, "run_id")`

Additionally, both test files write state fixtures with the old flat key and
assert against flat reads, so they will start failing once TASK-033 lands.

Inputs:
- `aiw/workflow/recovery.py` (TASK-018)
- `aiw/cli/tui.py` (TASK-024)
- `tests/test_recovery.py`
- `tests/test_tui.py`

Outputs (artifacts/files created or changed):
- `aiw/workflow/recovery.py`
- `aiw/cli/tui.py`
- `tests/test_recovery.py`
- `tests/test_tui.py`

File scope allowlist:
- aiw/workflow/recovery.py
- aiw/cli/tui.py
- tests/test_recovery.py
- tests/test_tui.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

---

## Required changes

### 1. `aiw/workflow/recovery.py`

Replace the flat read:

```python
run_id = str(payload.get("run_id") or "stale-execution-recovery")
```

With a nested read:

```python
metadata = payload.get("metadata") or {}
run_id = str(metadata.get("run_id") or "stale-execution-recovery")
```

No other changes to `recovery.py`.

---

### 2. `aiw/cli/tui.py`

Replace the flat read:

```python
run_id = _string_field(payload, "run_id")
```

With a nested read:

```python
metadata = payload.get("metadata") or {}
run_id = _string_field(metadata, "run_id") if isinstance(metadata, dict) else None
```

No other changes to `tui.py`.

---

### 3. `tests/test_recovery.py`

Update all state file fixtures that write `run_id` as a flat top-level key to
use the nested form:

```python
# Before
{"current_state": "EXECUTING", "run_id": "run-123", "state": "EXECUTING"}

# After
{"current_state": "EXECUTING", "metadata": {"run_id": "run-123"}, "state": "EXECUTING"}
```

Update the assertion on line 40 from:

```python
assert state["run_id"] == "run-123"
```

To:

```python
assert state.get("metadata", {}).get("run_id") == "run-123"
```

Note: `recover_stale_execution` calls `_write_state_payload(state_path, payload)`
with the mutated payload. After this task, the payload written to disk will have
`run_id` under `metadata`, not at the top level. The post-recovery state file
assertion must check the nested path, not the flat key.

Update the assertion that checks trace events carry the correct run_id — this
should already pass since the trace emitter receives `run_id` directly, but
verify it still holds.

Apply the same fixture update to any other tests in `test_recovery.py` that
write flat `run_id` in state payloads (check all `_init_repo` or inline
`write_text` calls).

---

### 4. `tests/test_tui.py`

Update all state file fixtures that write `run_id` as a flat top-level key to
use the nested form:

```python
# Before
{"current_state": "PLANNED", "run_id": "run-123", "state": "PLANNED"}

# After
{"current_state": "PLANNED", "metadata": {"run_id": "run-123"}, "state": "PLANNED"}
```

Update any assertions that check `"Run ID: run-123"` is present in the rendered
output — these should continue to pass after the read fix, but verify them.

Add one test (or update an existing one) that asserts: when the state file has
no `"metadata"` key, `render_status` does not include a `"Run ID:"` line.

---

## Constraints enforced

- `workflow.state_file`: `.aiw/workflow_state.json`

## Non-goals

- Do not change `WorkflowStateMachine` (TASK-033 is complete).
- Do not change `executor.py`.
- Do not change any other source files or test files.
- Do not add new metadata fields.
- Do not change the `_string_field` helper signature or behavior.

## Acceptance criteria (measurable)

- `recovery.py` reads `run_id` from `payload["metadata"]["run_id"]`.
- When state file has `metadata.run_id = "run-123"`, recovery trace events
  carry `run_id = "run-123"` (not the fallback string).
- When state file has no `metadata` key, recovery uses fallback
  `"stale-execution-recovery"`.
- `tui.py` renders `"Run ID: run-123"` when state file has
  `metadata.run_id = "run-123"`.
- `tui.py` omits the `"Run ID:"` line when state file has no `metadata` key.
- No flat `run_id` key in any state file fixture in `test_recovery.py` or
  `test_tui.py`.
- `pytest tests/test_recovery.py -q` passes.
- `pytest tests/test_tui.py -q` passes.
- `ruff check .` passes.
- `mypy aiw tests` passes.

## Tests / checks required

- `pytest tests/test_recovery.py -q`
- `pytest tests/test_tui.py -q`
- `ruff check .`
- `mypy aiw tests`

## Observability requirements

- None. The trace emitter receives `run_id` directly — this task only affects
  how `run_id` is read from the state file for the fallback/display paths.

## Rollback plan

- `git checkout` to pre-task baseline.
