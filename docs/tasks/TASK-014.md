## TASK-014: Fixer session integration

Type: IMPLEMENTATION
Depends_on: [TASK-013]

Objective:
Implement the Fixer session that is spawned only after a failed test run, produces a bounded fix patch within the same write scope, and emits the fixer_spawned trace event.

Context (spec refs):
- PRD §7.1 (optional Fixer session), §7.2 steps 8-9
- SDD §10.2 (Fixer session)
- ADR-010: Two-session Codex model

Inputs:
- Failed test output
- Task spec
- Original Coder patch context
- File scope allowlist

Outputs (artifacts/files created or changed):
- `aiw/orchestrator/fixer.py`
- `tests/test_fixer.py`

File scope allowlist:
- aiw/orchestrator/fixer.py
- tests/test_fixer.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `run_fixer_session(task_spec: TaskSpec, test_output: str, constraints: ConstraintsConfig) -> PatchResult`
- At most one invocation per task run.
- Same write scope as Coder session.
- Returns PatchResult.

Constraints enforced:
- `agents.task_scoped_coding_agent.no_cross_task_edits`
- `execution.max_iterations_per_task`

Non-goals:
- No iteration counting (done in TASK-015).
- No BLOCKED transition (done in TASK-016).

Acceptance criteria (measurable):
- Only spawnable after test failure.
- At most one Fixer session per run.
- Same file scope as Coder.
- Produces valid PatchResult.
- Emits fixer_spawned event data.

Tests / checks required:
- `pytest tests/test_fixer.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Returns data for `fixer_spawned` trace event.

Rollback plan:
- `git checkout` to pre-task baseline.
