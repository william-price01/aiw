## TASK-016: Blocker report and BLOCKED transition

Type: IMPLEMENTATION
Depends_on: [TASK-027]

Objective:
Implement generation of blocker reports, optional followup_tasks and scope_expansion_request reports on iteration exhaustion, and the BLOCKED state transition.

Context (spec refs):
- PRD §7.2 step 10 (blocker report), §7.5 (followup/scope expansion)
- SDD §9 step 8 (exhaustion reports)

Inputs:
- Execution context (task ID, test output, iterations used)
- Execution result from TASK-015

Outputs (artifacts/files created or changed):
- `aiw/orchestrator/blocker.py`
- `tests/test_blocker.py`
- Runtime: `docs/reports/TASK-###_blocker_report.md`, optionally `docs/reports/TASK-###_followup_tasks.md`, `docs/reports/TASK-###_scope_expansion_request.md`

File scope allowlist:
- aiw/orchestrator/blocker.py
- tests/test_blocker.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `generate_blocker_report(task_id: str, context: BlockerContext) -> Path`
- `generate_followup_tasks(task_id: str, context: BlockerContext) -> Path | None`
- `generate_scope_expansion_request(task_id: str, context: BlockerContext) -> Path | None`

Constraints enforced:
- Reports written to `docs/reports/` only.

Non-goals:
- No execution logic (done in TASK-015).
- No BLOCKED retry semantics (manual, per PRD §14).

Acceptance criteria (measurable):
- `docs/reports/TASK-###_blocker_report.md` generated on exhaustion.
- Report contains: task ID, iterations used, last test output, failure reason.
- Optional followup/scope reports generated when applicable.
- `blocked` trace event emitted.

Tests / checks required:
- `pytest tests/test_blocker.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Emits `blocked` trace event.

Rollback plan:
- `git checkout` to pre-task baseline.
