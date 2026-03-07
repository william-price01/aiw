## TASK-030: Wire blocker report generation into executor on exhaustion

Type: IMPLEMENTATION
Depends_on: [TASK-016, TASK-027]

Objective:
Call `generate_blocker_report` from `executor.py` at the BLOCKED transition point so that iteration exhaustion produces the required report artifact under `docs/reports/`.

Context (spec refs):
- PRD §7.2 step 10: "Generate `docs/reports/TASK-###_blocker_report.md`"
- SDD §9 step 8: reports emitted on exhaustion before transitioning to BLOCKED

Current state:
`executor.py` transitions to BLOCKED and emits the `blocked` trace event but never calls `generate_blocker_report`. `blocker.py` is fully implemented but orphaned — nothing calls it from the executor path.

Inputs:
- `aiw/orchestrator/executor.py` (existing)
- `aiw/orchestrator/blocker.py` (existing — `generate_blocker_report`, `BlockerContext`)

Outputs (artifacts/files created or changed):
- `aiw/orchestrator/executor.py`
- `tests/test_executor_fixer.py`

File scope allowlist:
- aiw/orchestrator/executor.py
- tests/test_executor_fixer.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
In the exhaustion branch of `execute_task`, after `_transition(..., "on:exhaustion")` and before the `blocked` trace event, add:

```python
from aiw.orchestrator.blocker import BlockerContext, generate_blocker_report
context = BlockerContext(
    root=repo_root,
    iterations_used=constraints.execution.max_iterations_per_task,
    last_test_output=fixed_test.output,
    failure_reason="iteration_exhausted",
)
generate_blocker_report(task_id, context)
```

Constraints enforced:
- Reports written to `docs/reports/` only (enforced by `blocker.py`).

Non-goals:
- No changes to `generate_blocker_report` signature or behavior.
- No `generate_followup_tasks` or `generate_scope_expansion_request` calls (those require richer context not available at the executor level and remain optional per spec).

Acceptance criteria (measurable):
- After a BLOCKED execution, `docs/reports/TASK-###_blocker_report.md` exists.
- Report contains the task ID, iterations used, and last test output.
- `test_executor_fixer.py` asserts the report file exists at the expected path after BLOCKED transition.

Tests / checks required:
- `pytest tests/test_executor_fixer.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- No new trace events. The `blocked` event is already emitted; this task adds the file artifact that must accompany it.

Rollback plan:
- `git checkout` to pre-task baseline.
