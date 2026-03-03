## TASK-013: Coder session integration

Type: IMPLEMENTATION
Depends_on: [TASK-009, TASK-010, TASK-011, TASK-012]

Objective:
Implement the Coder session that spawns exactly one Codex CLI invocation, passes the task spec as context, enforces the file scope allowlist, and returns a patch proposal.

Context (spec refs):
- PRD §7.1 (one Coder session per task run), §7.2 step 4 (spawn Coder)
- SDD §10.1 (Coder session), §12 (backend integration)
- ADR-010: Two-session Codex model
- constraints.yml: `agents.task_scoped_coding_agent`

Inputs:
- Task spec (docs/tasks/TASK-###.md)
- File scope allowlist from task spec
- Constraints config

Outputs (artifacts/files created or changed):
- `aiw/orchestrator/coder.py`
- `tests/test_coder.py`

File scope allowlist:
- aiw/orchestrator/coder.py
- tests/test_coder.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `run_coder_session(task_spec: TaskSpec, constraints: ConstraintsConfig) -> PatchResult`
- `PatchResult` contains: changed_files, diff_stats, success flag.
- Exactly one Codex CLI invocation.
- Patch validated by scope_validator before return.

Constraints enforced:
- `agents.task_scoped_coding_agent.enforced`
- `agents.task_scoped_coding_agent.no_cross_task_edits`
- `boundaries.internal_tool_state.coding_agents_must_not_write`

Non-goals:
- No fix logic (done in TASK-014).
- No test execution (done in TASK-015).
- No iteration loop (done in TASK-015).

Acceptance criteria (measurable):
- Spawns exactly one Codex CLI session.
- Passes task spec content to Codex.
- Enforces file scope allowlist on output.
- Returns structured PatchResult.
- Rejects patches touching forbidden paths.

Tests / checks required:
- `pytest tests/test_coder.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Caller emits trace events (scope_validation, diff_threshold_check).

Rollback plan:
- `git checkout` to pre-task baseline.
