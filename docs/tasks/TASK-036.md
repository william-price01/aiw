## TASK-036: Consolidate remaining raw state write paths through WorkflowStateMachine.save()

Type: IMPLEMENTATION
Depends_on: [TASK-035]

Objective:
Route all remaining raw state file writes through `WorkflowStateMachine.save()` so there is a
single authoritative write path for `.aiw/workflow_state.json` across the entire codebase.
Remove the local `_write_current_state()` / `save_current_state()` helpers and the `state` fallback
read paths in the modules affected.

Context (spec refs):
- ADR-003: Explicit workflow state machine (state persisted via WorkflowStateMachine)
- SDD §5 (global workflow state machine — persisted in .aiw/workflow_state.json)
- constraints.yml: `workflow.state_file`

---

## Background / root cause

TASK-035 fixes the raw write in `recovery.py`. Four additional modules bypass
`WorkflowStateMachine.save()` and write the state file directly, using inconsistent schemas:

| Module | Write function | Schema written |
|---|---|---|
| `aiw/cli/init_cmd.py` | inline `write_text` | `{"state": "INIT"}` — missing `current_state` |
| `aiw/orchestrator/spec_phase.py` | `_write_current_state()` | `{"current_state": s, "state": s}` |
| `aiw/orchestrator/decompose.py` | `_write_current_state()` | `{"current_state": s, "state": s}` |
| `aiw/workflow/change_request.py` | `save_current_state()` | `{"current_state": s, "state": s}` |

`WorkflowStateMachine.save()` writes only `{"current_state": s}` (plus `metadata` when present).
`WorkflowStateMachine.load()` reads only `current_state` — it has no `state` fallback.

This means loading state via `WorkflowStateMachine.load()` will fail on a file written by
`init_cmd.py` (missing `current_state`), and the dual-key files are schema-inconsistent with
`save()` output. Every module that reads state also carries a `state`-key fallback read path that
compensates for these inconsistent writes. After this task, those fallback paths become dead code
and must be removed.

Note: `init_cmd.py` is the only writer that does NOT include `current_state` at all. This is a
hard bug: `WorkflowStateMachine.load()` will raise on a state file written by `aiw init`.

---

## What (required behavior — unchanged)

- `aiw init` must create `.aiw/workflow_state.json` with state `INIT`.
- Spec-phase draft and approve commands must persist the correct resulting state after each
  transition.
- `aiw decompose` must persist `PLANNED` after a successful decompose.
- `aiw request-change` must persist the rollback state after applying a change request.
- All of the above already happen correctly. Only the write mechanism changes.

No behavioral change. This is a HOW-level fix only.

---

## Inputs:
- `aiw/cli/init_cmd.py`
- `aiw/orchestrator/spec_phase.py`
- `aiw/orchestrator/decompose.py`
- `aiw/workflow/change_request.py`
- `aiw/workflow/state_machine.py` (WorkflowStateMachine.save(), .load())
- Corresponding test files

## Outputs (artifacts/files created or changed):
- `aiw/cli/init_cmd.py` (fixed)
- `aiw/orchestrator/spec_phase.py` (fixed)
- `aiw/orchestrator/decompose.py` (fixed)
- `aiw/workflow/change_request.py` (fixed)
- `tests/test_init.py` (regression tests)
- `tests/test_spec_draft_cmds.py` (regression tests)
- `tests/test_spec_approve_cmds.py` (regression tests)
- `tests/test_decompose_orchestration.py` (regression tests)
- `tests/test_change_request.py` (regression tests)

## File scope allowlist:
- aiw/cli/init_cmd.py
- aiw/orchestrator/spec_phase.py
- aiw/orchestrator/decompose.py
- aiw/workflow/change_request.py
- tests/test_init.py
- tests/test_spec_draft_cmds.py
- tests/test_spec_approve_cmds.py
- tests/test_decompose_orchestration.py
- tests/test_change_request.py

## Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

---

## Required changes per module

### `aiw/cli/init_cmd.py`

Replace the inline `json.dumps({"state": "INIT"}, ...)` write with:

```python
from aiw.workflow.state_machine import WorkflowStateMachine
WorkflowStateMachine(current_state="INIT").save(state_file)
```

Remove the `import json` if it is no longer needed.

### `aiw/orchestrator/spec_phase.py`

- Replace every call to `_write_current_state(state_path, next_state)` with
  `machine.save(state_path)` (the `machine` instance already holds `next_state` after `.transition()`).
- Remove `_write_current_state()` function.
- Remove `_read_current_state()` function and its `state`-key fallback; replace call sites with
  `WorkflowStateMachine.load(state_path).current_state`.
- Remove `import json` if no longer needed.

### `aiw/orchestrator/decompose.py`

- Replace every call to `_write_current_state(state_path, next_state)` with
  `machine.save(state_path)`.
- Remove `_write_current_state()` function.
- Remove `_read_current_state()` function and its `state`-key fallback; replace call sites with
  `WorkflowStateMachine.load(state_path).current_state`.
- Remove `import json` if no longer needed.

### `aiw/workflow/change_request.py`

- Replace `save_current_state(state_path, machine.current_state)` with
  `machine.save(state_path)`.
- Remove `save_current_state()` function.
- Remove `load_current_state()` function and its `state`-key fallback; replace call sites with
  `WorkflowStateMachine.load(state_path).current_state`.
- Remove `import json` if no longer needed.

### Fallback read paths in non-target modules

`aiw/cli/main.py`, `aiw/cli/tui.py`, `aiw/cli/undo_cmd.py` each contain local
`_read_current_state()` helpers with a `state`-key fallback. These become dead code after this
fix. However, they are outside the file scope allowlist for this task. Do NOT edit them here.
A follow-on cleanup can address them, or they can be left as harmless dead fallbacks.

---

## Constraints enforced:
- `workflow.state_file`: `.aiw/workflow_state.json`
- `boundaries.internal_tool_state.writer`: aiw_only

## Non-goals:
- No changes to `WorkflowStateMachine` itself.
- No changes to the fallback read paths in `main.py`, `tui.py`, `undo_cmd.py` (outside scope).
- No behavioral change to any command.
- No changes to `recovery.py` (covered by TASK-035).

---

## Acceptance criteria (measurable):

1. After `aiw init`, `WorkflowStateMachine.load(state_path).current_state == "INIT"` succeeds
   without error.
2. After `aiw init`, the state file contains `current_state` and does NOT contain a bare `state`
   key at the top level.
3. After any spec-phase draft or approve command, the state file schema matches
   `WorkflowStateMachine.save()` output: `current_state` key only (plus `metadata` if present).
4. After `aiw decompose` succeeds, the state file contains `current_state: "PLANNED"` only.
5. After `aiw request-change`, the state file contains `current_state` only.
6. `_write_current_state()` does not exist in `spec_phase.py` or `decompose.py`.
7. `save_current_state()` and `load_current_state()` do not exist in `change_request.py`.
8. All existing tests for affected modules pass without modification to their assertions.
9. New regression tests in each affected test file verify:
   - State file written by that module contains `current_state` and no bare `state` key.
   - `WorkflowStateMachine.load()` on the written file succeeds and returns the expected state.

## Tests / checks required:
- `pytest tests/test_init.py tests/test_spec_draft_cmds.py tests/test_spec_approve_cmds.py tests/test_decompose_orchestration.py tests/test_change_request.py -q`
- `ruff check .`
- `mypy aiw tests`

## Observability requirements:
- None. No trace emission changes.

## Rollback plan:
- `git checkout` to pre-task baseline.
