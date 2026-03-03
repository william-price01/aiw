## TASK-027: Execution loop — Fixer path, iteration cap, BLOCKED

Type: IMPLEMENTATION
Depends_on: [TASK-015]

Objective:
Extend the execution loop to handle the failure path: on test failure spawn Fixer session, apply fix, re-run tests, enforce iteration cap (max 3), and transition to BLOCKED on exhaustion.

Context (spec refs):
- PRD §7.1–7.2 steps 8–10 (failure/exhaustion path)
- SDD §9 steps 6–8
- constraints.yml: `execution.max_iterations_per_task`

Inputs:
- Executor from TASK-015
- Fixer session (TASK-014)
- Trace emitter (TASK-010)

Outputs (artifacts/files created or changed):
- `aiw/orchestrator/executor.py` (extended)
- `tests/test_executor_fixer.py`

File scope allowlist:
- aiw/orchestrator/executor.py
- tests/test_executor_fixer.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- Extends `execute_task` to handle failure path.
- On test FAIL after Coder:
  1. Spawn Fixer session.
  2. Validate fix patch.
  3. Apply fix.
  4. Re-run tests.
  5. If PASS → PLANNED.
  6. If still FAIL → check iteration count.
- On iteration exhaustion (3): transition EXECUTING → BLOCKED.
- At most one Fixer session per run.

Constraints enforced:
- `execution.max_iterations_per_task`: 3
- `workflow.transitions`: EXECUTING → BLOCKED (exhaustion)

Non-goals:
- No blocker report generation (done in TASK-016).
- No capsule log (done in TASK-020).

Acceptance criteria (measurable):
- On test FAIL: Fixer session spawned.
- Fix patch validated within same scope.
- On fix PASS: transitions EXECUTING → PLANNED.
- On exhaustion (3 iterations): transitions EXECUTING → BLOCKED.
- At most one Fixer session per run.
- Emits: test_run_failed, fixer_spawned, iteration_exhausted, blocked.

Tests / checks required:
- `pytest tests/test_executor_fixer.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Trace events for failure path: test_run_failed, fixer_spawned, iteration_exhausted, blocked.

Rollback plan:
- `git checkout` to pre-task baseline.
