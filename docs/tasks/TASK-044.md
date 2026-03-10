## TASK-044: Remove Fixer session and iteration cap

Type: IMPLEMENTATION
Depends_on: [TASK-038]

Objective:
Remove the Fixer session, `max_iterations_per_task`, and all associated logic from the AIW
codebase. Each `aiw go` run now permits exactly one Coder session: PASS or BLOCKED, no retries.
This implements ADR-013 and supersedes ADR-010.

Context (spec refs):
- ADR-013: Single Coder Session — No Fixer, No Iteration Cap
- PRD §7 (updated execution flow)
- SDD §10 (updated Codex session model)

---

## What changes

### Delete

- `aiw/orchestrator/fixer.py` — entire module removed
- `tests/test_fixer.py` — entire file removed
- `tests/test_executor_fixer.py` — entire file removed

### Modify

**`docs/constraints.yml`**
- Remove `execution.max_iterations_per_task`
- Remove `fixer_spawned` and `iteration_exhausted` from `observability.traces.required_events`

**`aiw/infra/constraints.py`**
- Remove `max_iterations_per_task: int` from `ExecutionConfig` dataclass
- Remove loader call for `execution.max_iterations_per_task`

**`aiw/infra/trace.py`**
- Remove `"fixer_spawned"` and `"iteration_exhausted"` from `REQUIRED_EVENTS` (or equivalent constant/set)

**`aiw/orchestrator/executor.py`**
- Remove import of `fixer.py` (`build_fixer_spawned_event_data`, `run_fixer_session`)
- Remove `FixerRunner` type alias
- Remove `fixer_runner: FixerRunner | None` parameter from `execute_task()`
- Remove `_default_fixer_runner()` function
- Remove `run_fixer` call and entire Fixer execution branch (lines after initial test failure)
- On test failure: transition directly to BLOCKED (call existing `_handle_blocked_result()` or equivalent)
- Remove `iterations_used` field from `ExecutionResult`
- Remove all `iterations_used` and `max_iterations_per_task` references from event payloads
- The `failure_reason` in the BLOCKED payload on test failure becomes `"test_failed"`
  (replacing `"iteration_exhausted"`)

**`aiw/orchestrator/blocker.py`**
- Remove `iterations_used: int` from `BlockerContext` dataclass
- Remove all `iterations_used` references from report generation strings
- Update any `"iteration_exhausted"` literal → `"test_failed"` in report text

**`aiw/tasks/capsule_log.py`**
- Remove `iterations_used` line from log output
- Remove `iterations_used` from `ExecutionResult` usage (field no longer exists)

**`tests/test_executor_happy.py`**
- Remove `assert result.iterations_used == 1` (field no longer exists)

**`tests/test_blocker.py`**
- Remove `iterations_used=3` (and all `iterations_used` values) from `BlockerContext` fixtures
- Update `failure_reason="iteration_exhausted"` → `failure_reason="test_failed"` in all fixtures
- Update string assertions: `"iteration_exhausted"` → `"test_failed"` wherever it appears in
  report content assertions

**`tests/test_capsule_log.py`**
- Remove `iterations_used` from all `ExecutionResult` fixture constructors
- Remove any assertions that reference `iterations_used`

**`tests/integration/test_error_paths.py`**
- Remove mock of `aiw.orchestrator.executor.run_fixer_session`
- Remove assertions on `fixer_spawned` trace event
- Remove assertions on `"iteration_exhausted"` in blocker report and trace events
- Update BLOCKED path test: Coder produces failing patch → tests fail → BLOCKED directly
  (no Fixer step). Assert `failure_reason == "test_failed"` in trace and blocker report.
- Retain all other error path tests (invalid state transitions, lock violations, diff threshold,
  stale recovery, constraints gate) — these are unaffected.

---

## Inputs:
- All files listed under "Modify" and "Delete" above

## Outputs (artifacts/files created or changed):
- `aiw/orchestrator/executor.py`
- `aiw/infra/constraints.py`
- `aiw/infra/trace.py`
- `aiw/orchestrator/blocker.py`
- `aiw/tasks/capsule_log.py`
- `tests/test_executor_happy.py`
- `tests/test_blocker.py`
- `tests/test_capsule_log.py`
- `tests/integration/test_error_paths.py`
- `docs/constraints.yml`
- Deleted: `aiw/orchestrator/fixer.py`
- Deleted: `tests/test_fixer.py`
- Deleted: `tests/test_executor_fixer.py`

## File scope allowlist:
- aiw/orchestrator/executor.py
- aiw/infra/constraints.py
- aiw/infra/trace.py
- aiw/orchestrator/blocker.py
- aiw/tasks/capsule_log.py
- tests/test_executor_happy.py
- tests/test_blocker.py
- tests/test_capsule_log.py
- tests/integration/test_error_paths.py
- docs/constraints.yml
- aiw/orchestrator/fixer.py (delete)
- tests/test_fixer.py (delete)
- tests/test_executor_fixer.py (delete)

## Locked artifacts confirmation:
- docs/constraints.yml is modified here as part of the spec change driven by ADR-013.
  This is an authorized change — the iteration cap removal is the explicit goal of this task.
  No change request file is required because the ADR is the governing document.
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**

## Interfaces/contracts:

Post-refactor `execute_task()` signature:
```python
def execute_task(
    task_id: str,
    root: Path,
    coder_runner: CoderRunner | None = None,
) -> ExecutionResult:
```

Post-refactor `ExecutionResult`:
```python
@dataclass
class ExecutionResult:
    status: Literal["PASS", "BLOCKED"]
    run_id: str
    task_id: str
```
No `iterations_used` field.

Post-refactor `BlockerContext`:
```python
@dataclass
class BlockerContext:
    task_id: str
    run_id: str
    failure_reason: str   # "test_failed" | "patch_validation_failed" | "coder_session_error"
    last_test_output: str
```
No `iterations_used` field.

Post-refactor required trace events (12 total, down from 14):
```
state_transition
constraint_validation
scope_validation
diff_threshold_check
test_run_started
test_run_failed
test_run_passed
blocked
run_complete
task_marked_complete
quality_gate_failed
lock_violation_hard_fail
```
Removed: `fixer_spawned`, `iteration_exhausted`

Execution flow (post-refactor):
1. Validate state = PLANNED.
2. Pass constraints gate + task lint.
3. Generate run_id, write to state + JSONL header.
4. Create pre-task checkpoint.
5. Transition to EXECUTING.
6. Run Coder session → validate patch → apply patch.
7. Run tests.
8. If PASS → append completion record, emit `task_marked_complete`, transition to PLANNED, emit `run_complete`.
9. If FAIL → emit `test_run_failed`, emit `blocked` with `failure_reason="test_failed"`, transition to BLOCKED, emit `run_complete`.

## Constraints enforced:
- All existing tests not listed in "Modify" above must continue to pass without changes.
- No new behavior is introduced — this is removal only.
- The BLOCKED transition on test failure must use `failure_reason="test_failed"`, not `"iteration_exhausted"`.

## Non-goals:
- No new quality gates (slopgate etc. — future extension).
- No changes to the Coder session itself (`coder.py` unchanged).
- No changes to any other executor behavior (checkpoint, scope validation, lock checks).
- No changes to CLI commands, state machine, or TUI.

## Acceptance criteria (measurable):
1. `pytest -q` passes across the full test suite with no fixer-related tests present.
2. `aiw go TASK-###` with a failing test run → state=BLOCKED, blocker report generated, `failure_reason="test_failed"` in trace.
3. `aiw go TASK-###` with a passing test run → state=PLANNED, completion record appended.
4. `from aiw.orchestrator.fixer import ...` raises `ModuleNotFoundError` (file deleted).
5. `constraints.yml` loads without error after `max_iterations_per_task` removal.
6. `ConstraintsConfig` has no `max_iterations_per_task` field.
7. Trace emitter accepts all 12 required events; rejects `fixer_spawned` and `iteration_exhausted` as unknown event types (or simply no longer references them).
8. Blocker report contains no "Iterations used" line.
9. Capsule log contains no "Iterations used" line.
10. `ruff check .` passes.
11. `mypy aiw tests` passes.

## Tests / checks required:
- `pytest -q` (full suite)
- `ruff check .`
- `mypy aiw tests`

## Observability requirements:
- `blocked` trace event emitted with `failure_reason="test_failed"` on test failure.
- `fixer_spawned` and `iteration_exhausted` no longer emitted by anything.

## Rollback plan:
- `git checkout` to pre-task baseline.
