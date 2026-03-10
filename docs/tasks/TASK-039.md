## TASK-039: DAG executor — `aiw run` command

Type: IMPLEMENTATION
Depends_on: [TASK-038]

Objective:
Implement the `aiw run` command that autonomously walks `docs/tasks/DAG.yml` in topological
order, parallelizes independent layers where file-scope permits, invokes the existing
`execute_task()` loop per task, pauses on BLOCKED, and resumes on operator resolution.

Context (spec refs):
- PRD §14 (DAG Executor)
- SDD §18 (DAG Executor)
- constraints.yml: `workflow.allowed_commands_by_state.PLANNED`
- DAG.yml: dependency graph and filescope per task

Inputs:
- `docs/tasks/DAG.yml` (dependency graph)
- `docs/tasks/COMPLETED.md` (already-passed tasks)
- `aiw/orchestrator/executor.py` (`execute_task()` — existing, unchanged)
- Current workflow state

Outputs (artifacts/files created or changed):
- `aiw/orchestrator/dag_executor.py`
- `aiw/cli/run_cmd.py`
- `tests/test_dag_executor.py`

File scope allowlist:
- aiw/orchestrator/dag_executor.py
- aiw/cli/run_cmd.py
- tests/test_dag_executor.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:

`DagExecutor`:
- `__init__(dag_path: Path, completed_path: Path, root: Path)`
- `run() -> DagRunResult` — execute all pending tasks in topological order.
- `resume() -> DagRunResult` — re-enter after BLOCKED resolution; skips PASSED tasks.
- `_compute_ready_set(passed: set[str]) -> list[list[str]]` — returns ordered layers of ready tasks.
- `_has_filescope_collision(task_a: str, task_b: str) -> bool` — checks DAG.yml filescope overlap.

`DagRunResult`:
- `status: Literal["COMPLETE", "PAUSED"]`
- `passed: list[str]`
- `blocked: list[str]`
- `summary: str`

`run_dag(root: Path, resume: bool = False) -> DagRunResult` — top-level entry called by CLI.

CLI:
- `aiw run` — starts a fresh DAG run from PLANNED.
- `aiw run --resume` — resumes a paused DAG run after BLOCKED resolution.

Topological ordering:
- Use Kahn's algorithm on the `depends_on` edges in DAG.yml.
- Tasks with all dependencies PASSED enter the ready set.
- Tasks already in COMPLETED.md are skipped.

Parallelization:
- Tasks in the same ready layer with no filescope overlap may run concurrently.
- Use `concurrent.futures.ThreadPoolExecutor`.
- Tasks with any filescope overlap in the same layer are serialized.
- No cross-layer parallelism.

BLOCKED handling:
- On any task transition to BLOCKED: emit `dag_task_blocked`, print blocker summary to stdout.
- Halt advancement of dependent tasks.
- Independent tasks already running in the current layer may complete.
- Exit `run()` with `DagRunResult(status="PAUSED")`.
- `aiw run --resume` re-enters with updated completion set.

Observability trace events emitted:
- `dag_run_started`: `{total_tasks, layer_count}`
- `dag_layer_started`: `{layer_index, task_ids}`
- `dag_task_blocked`: `{task_id, blocker_report_path}`
- `dag_run_complete`: `{passed_count, summary}`
- `dag_run_paused`: `{blocked_task_id}`

Constraints enforced:
- `aiw run` refused unless state = PLANNED.
- No new workflow states introduced.
- Between task completions, state returns to PLANNED (existing transition semantics).
- `execute_task()` is called unmodified; DAG executor is scheduling wrapper only.
- File-scope collision detection is pre-launch only; no runtime locking.

Non-goals:
- No cross-layer parallelism.
- No dynamic re-decomposition during a run.
- No new execution loop logic (reuses executor.py).
- No canvas integration (done in TASK-041).
- No modification to executor.py, go_cmd.py, or state_machine.py.

Acceptance criteria (measurable):
1. `aiw run` in PLANNED state walks all pending tasks in DAG topological order.
2. Independent tasks within the same layer execute concurrently (verified by timing or mock ordering).
3. Tasks with filescope overlap in the same layer are serialized.
4. On task BLOCKED: run pauses, blocker summary printed, `DagRunResult(status="PAUSED")` returned.
5. `aiw run --resume` skips already-PASSED tasks and resumes from the correct frontier.
6. `aiw run` refused outside PLANNED state (exit code 1).
7. All five DAG trace events emitted correctly.
8. Tasks already in COMPLETED.md are not re-executed.
9. On all tasks PASSED: `DagRunResult(status="COMPLETE")` returned.

Tests / checks required:
- `pytest tests/test_dag_executor.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Emits: dag_run_started, dag_layer_started, dag_task_blocked, dag_run_complete, dag_run_paused.

Rollback plan:
- `git checkout` to pre-task baseline.
