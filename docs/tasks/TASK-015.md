## TASK-015: Execution loop — happy path (Coder → PASS)

Type: IMPLEMENTATION
Depends_on: [TASK-013, TASK-014]

Objective:
Implement the execution loop for the happy path: validate state, create checkpoint, generate run_id, transition to EXECUTING, run Coder session, validate patch, run tests, and on PASS transition to PLANNED.

Context (spec refs):
- PRD §7.1–7.2 steps 1–7 (happy path)
- SDD §5.2 (EXECUTING entry semantics), §9 steps 1–5
- constraints.yml: `execution.run_id`, `workflow.transitions`

Inputs:
- Task ID (TASK-###)
- Coder session (TASK-013)
- Checkpoint (TASK-011), Trace emitter (TASK-010), Scope validator (TASK-012)

Outputs (artifacts/files created or changed):
- `aiw/orchestrator/executor.py`
- `aiw/cli/go_cmd.py`
- `tests/test_executor_happy.py`

File scope allowlist:
- aiw/orchestrator/executor.py
- aiw/cli/go_cmd.py
- tests/test_executor_happy.py
- docs/tasks/COMPLETED.md

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `execute_task(task_id: str, root: Path) -> ExecutionResult`
- `ExecutionResult`: status (PASS), iterations_used, run_id.
- Happy-path flow:
  1. Validate state=PLANNED.
  2. Pass constraints gate + task lint.
  3. Generate run_id UUID, write to state + JSONL header.
  4. Create pre-task checkpoint.
  5. Transition to EXECUTING.
  6. Run Coder session → validate patch → apply → run tests.
  7. On PASS → append completion record to docs/tasks/COMPLETED.md, emit task_marked_complete, transition to PLANNED, terminate.

Constraints enforced:
- `execution.run_id.required`
- `execution.run_id.write_on_enter_EXECUTING`
- `workflow.transitions`: PLANNED→EXECUTING, EXECUTING→PLANNED (success)
- `boundaries.locked_artifacts.mutable_during_execution_append_only`: docs/tasks/COMPLETED.md

Non-goals:
- No Fixer path (done in TASK-027).
- No iteration cap logic (done in TASK-027).
- No BLOCKED transition (done in TASK-027).
- No blocker report (done in TASK-016).
- No capsule log / TASK-###.log.md (done in TASK-020).

Acceptance criteria (measurable):
- Refused unless state=PLANNED.
- Generates UUID run_id.
- Creates pre-task checkpoint.
- Transitions PLANNED → EXECUTING.
- On test PASS: appends one record to docs/tasks/COMPLETED.md with task ID, run ID, timestamp, and result.
- On test PASS: transitions EXECUTING → PLANNED.
- Emits: state_transition, test_run_started, test_run_passed, task_marked_complete, run_complete.

Tests / checks required:
- `pytest tests/test_executor_happy.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Full trace event emission for happy path events including task_marked_complete.

Rollback plan:
- `git checkout` to pre-task baseline.
