## TASK-020: Capsule log writer (append-only)

Type: IMPLEMENTATION
Depends_on: [TASK-027]

Objective:
Implement the per-task capsule log that records chosen task, constraints snapshot hash, diff summaries, test results, and PASS/BLOCKED termination in append-only markdown.

Context (spec refs):
- PRD §7.4 (task capsule log contents)
- constraints.yml: `agents.task_scoped_coding_agent.memory`

Inputs:
- Execution result from TASK-015
- Constraints config hash
- Diff summaries per iteration
- Test results per iteration

Outputs (artifacts/files created or changed):
- `aiw/tasks/capsule_log.py`
- `tests/test_capsule_log.py`
- Runtime: `docs/tasks/TASK-###.log.md`

File scope allowlist:
- aiw/tasks/capsule_log.py
- tests/test_capsule_log.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `write_capsule_log(task_id: str, run_result: ExecutionResult, output_dir: Path) -> Path`
- Append-only: new runs append, never overwrite.
- Path template: `docs/tasks/{TASK_ID}.log.md`

Constraints enforced:
- `agents.task_scoped_coding_agent.memory.type`: markdown_capsule
- `agents.task_scoped_coding_agent.memory.path_template`
- `agents.task_scoped_coding_agent.memory.append_only`

Non-goals:
- No execution logic.
- No cross-task log access.

Acceptance criteria (measurable):
- Writes `docs/tasks/TASK-###.log.md`.
- Contains: chosen task, constraints hash, diff summaries, test results, PASS/BLOCKED.
- Second run appends; does not overwrite first entry.
- Valid markdown format.

Tests / checks required:
- `pytest tests/test_capsule_log.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Log file is the observability artifact.

Rollback plan:
- `git checkout` to pre-task baseline.
