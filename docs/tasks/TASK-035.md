## TASK-035: Fix recovery.py state write path and remove dual-key inconsistency

Type: IMPLEMENTATION
Depends_on: [TASK-034]

Objective:
Route `recover_stale_execution()` state writes through `WorkflowStateMachine.save()` instead of the
raw `_write_state_payload()` path, and remove the dual `state`/`current_state` key write that
results from the bypass. This establishes a single authoritative write path for the state file.

Context (spec refs):
- SDD §5.3 (crash / stale EXECUTING determinism — state must transition deterministically to BLOCKED)
- ADR-011: Deterministic crash handling
- ADR-003: Explicit workflow state machine (state persisted via WorkflowStateMachine.save())
- constraints.yml: `workflow.state_file`, `execution.stale_execution_policy`

---

## Background / root cause

`recover_stale_execution()` in `aiw/workflow/recovery.py` correctly uses `WorkflowStateMachine`
to compute and validate the EXECUTING → BLOCKED transition, but then writes the resulting state
back to disk by directly mutating the raw payload dict and calling the private
`_write_state_payload()` helper:

```python
payload["current_state"] = next_state   # TASK-034 write
payload["state"] = next_state           # redundant legacy write
_write_state_payload(state_path, payload)
```

This creates a second authoritative write path for `.aiw/workflow_state.json` that:

1. Bypasses `WorkflowStateMachine.save()`, which is the canonical write path used everywhere else.
2. Writes both `state` and `current_state` keys, where `WorkflowStateMachine.save()` writes only
   `current_state`. This means the schema of the state file differs depending on which code path
   last wrote it.
3. Forces `_extract_current_state()` to maintain a `state`-key fallback read path, which becomes
   dead code once the dual write is removed.

The fix is straightforward: construct a `WorkflowStateMachine` from the loaded payload (including
existing metadata), call `machine.save(state_path)` after the transition, and remove the manual
dict mutations and `_write_state_payload()` call from the write step.

---

## What (required behavior — unchanged)

These invariants must continue to hold after the fix:

- If `state=EXECUTING` at startup: transitions to `BLOCKED`. (ADR-011, SDD §5.3)
- Emits `stale_execution_detected` trace event.
- No automatic resume.
- User must manually resolve before returning to `PLANNED`.
- Existing metadata (including `run_id`) is preserved across the recovery write.

No behavioral change. This is a HOW-level fix only.

---

## Inputs:
- `aiw/workflow/recovery.py` (current implementation)
- `aiw/workflow/state_machine.py` (`WorkflowStateMachine.save()`, `.load()`, metadata API)
- `tests/test_recovery.py` (existing tests — must continue to pass)

## Outputs (artifacts/files created or changed):
- `aiw/workflow/recovery.py` (fixed)
- `tests/test_recovery.py` (extended with regression tests for schema consistency)

## File scope allowlist:
- aiw/workflow/recovery.py
- tests/test_recovery.py

## Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

---

## Interfaces/contracts:

Public interface is unchanged:

```python
def check_stale_execution(state_path: Path) -> bool: ...
def recover_stale_execution(state_path: Path) -> None: ...
```

Internal changes:

1. In `recover_stale_execution()`:
   - After computing `next_state` via `machine.transition(...)`, call `machine.save(state_path)`
     instead of mutating `payload` and calling `_write_state_payload()`.
   - Metadata (including `run_id`) must be preserved. Load the machine with existing metadata
     before calling `save()`. `WorkflowStateMachine.load()` already handles this.
   - Remove the `payload["state"] = next_state` and `payload["current_state"] = next_state`
     mutation lines.
   - Remove the `_write_state_payload(state_path, payload)` call from the write step.

2. In `_extract_current_state()`:
   - Remove the `state` key fallback. Read only `current_state`.
   - If `current_state` is absent or not a string, raise `ValueError` (same as now, just no
     fallback).

3. `_write_state_payload()` may remain in the file if it is still used elsewhere (e.g., for
   recovery of a missing state file), but it must not be called from the state-write step.
   If it is used nowhere after the fix, remove it. Do not leave it as dead code.

---

## Constraints enforced:
- `execution.stale_execution_policy.on_detect_executing_at_startup.transition_to`: BLOCKED
- `execution.stale_execution_policy.on_detect_executing_at_startup.emit_event`: stale_execution_detected
- `workflow.state_file`: `.aiw/workflow_state.json`

## Non-goals:
- No behavioral change to stale recovery semantics.
- No changes to `WorkflowStateMachine` itself.
- No changes to how `check_stale_execution()` reads the state file.
- No changes to trace emission logic (run_id extraction, event payload, etc.).
- No migration of existing state files on disk.
- No changes to any other module.

---

## Acceptance criteria (measurable):

1. `recover_stale_execution()` no longer calls `_write_state_payload()` in its write step.
2. After recovery, the state file written to disk matches the schema produced by
   `WorkflowStateMachine.save()`: contains `current_state` key, does NOT contain a bare `state`
   key at the top level.
3. After recovery, `WorkflowStateMachine.load(state_path).current_state == "BLOCKED"`.
4. After recovery, existing `metadata` (e.g., `run_id`) in the state file is preserved.
5. `_extract_current_state()` no longer falls back to the `state` key.
6. All existing `tests/test_recovery.py` tests pass without modification to their assertions.
7. New regression tests added to `tests/test_recovery.py`:
   - A state file written by `recover_stale_execution()` contains `current_state` and no bare
     `state` key.
   - `WorkflowStateMachine.load()` on a post-recovery state file returns `current_state="BLOCKED"`.
   - Metadata (`run_id`) present before recovery is present in the post-recovery state file.

## Tests / checks required:
- `pytest tests/test_recovery.py -q`
- `ruff check .`
- `mypy aiw tests`

## Observability requirements:
- Unchanged. Trace emission logic is not modified.

## Rollback plan:
- `git checkout` to pre-task baseline.
