## TASK-040: Canvas API server

Type: IMPLEMENTATION
Depends_on: [TASK-039, TASK-043]

Objective:
Implement the thin local HTTP server (FastAPI) that exposes AIW state, task artifacts, trace
events, and coding session logs as JSON/SSE endpoints; accepts command requests that shell out
to the AIW CLI; exposes per-artifact spec chat endpoints; and streams live state and session
output via SSE.

Context (spec refs):
- PRD §15 (Canvas), §15.3.1 (Session Visibility)
- SDD §19.2 (Canvas API server), §19.2.1 (Session Capture Architecture)

Inputs:
- `.aiw/workflow_state.json`
- `docs/tasks/DAG.yml`, `docs/tasks/TASK-###.md`, `docs/tasks/COMPLETED.md`
- `.aiw/runs/*.jsonl`
- `.aiw/runs/session-<run_id>-{coder,fixer}.log` (from TASK-043)
- `aiw/infra/session_capture.py` (`SessionCapture.read_log()`, `SessionCapture.is_active()`)
- `aiw/orchestrator/spec_phase.py` (`SpecDraftSession` — existing, unchanged)
- AIW CLI entry point (`aiw` command)

Outputs (artifacts/files created or changed):
- `aiw/canvas/__init__.py`
- `aiw/canvas/server.py`
- `tests/test_canvas_server.py`

File scope allowlist:
- aiw/canvas/__init__.py
- aiw/canvas/server.py
- tests/test_canvas_server.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:

Read endpoints (all return JSON):
- `GET /api/state` → `{state: str, run_id: str | null, task_id: str | null}`
- `GET /api/tasks` → `[{id, title, type, depends_on, status}]` (status derived from COMPLETED.md)
- `GET /api/tasks/{task_id}` → `{id, content: str}` (raw markdown)
- `GET /api/tasks/{task_id}/log` → `{id, content: str}` (capsule log markdown, empty if absent)
- `GET /api/dag` → parsed DAG.yml as JSON
- `GET /api/runs` → `[{run_id, path, timestamp}]`
- `GET /api/runs/{run_id}` → `[{timestamp, event_type, run_id, payload}]`
- `GET /api/completed` → `[{task_id, run_id, completed_at, result, notes}]`
- `GET /api/sessions/{run_id}` → `{run_id, content: str, active: bool}`. Returns `content: ""` and `active: false` if the coder session log file does not yet exist.

Write endpoints (shell out to AIW CLI via `subprocess.run`):
- `POST /api/run` → shells `aiw run`; returns `{ok: bool, stdout, stderr}`
- `POST /api/run/resume` → shells `aiw run --resume`
- `POST /api/go/{task_id}` → shells `aiw go {task_id}`
- `POST /api/approve/{artifact}` → shells `aiw approve-{artifact}`
- `POST /api/request-change` with body `{target, reason, impact}` → shells `aiw request-change`
- `POST /api/command` with body `{command: str, args: list[str]}` → generic passthrough

No write endpoint may directly modify `.aiw/`, `docs/`, or any AIW artifact. All mutations go through CLI subprocess.

Spec chat endpoints:
- `POST /api/spec/chat/{artifact}` where artifact ∈ {prd, sdd, adrs, constraints}
- Request body: `{message: str, document: str, history: list[{role, content}]}`
- Invokes `SpecDraftSession` from `aiw/orchestrator/spec_phase.py` with appropriate system prompt for the artifact.
- Returns: `{reply: str, updated_document: str}`
- The AI session is stateless per request; full history passed in on each call.
- Refused if the artifact is not in its corresponding DRAFT state (returns HTTP 409 with reason).

SSE live state endpoint:
- `GET /api/events` — SSE stream.
- Polls `.aiw/workflow_state.json` and the most recent `.aiw/runs/*.jsonl` file at 1-second intervals.
- Emits `state_changed` event on workflow state change.
- Emits `trace_event` for each new line appended to the active JSONL trace.
- Tails the active session log file (`.aiw/runs/session-<run_id>-coder.log`) when present. New bytes read from the file are emitted as `session_output` events with payload `{run_id: str, chunk: str}`. Polling interval: 100ms for the session log (faster than state polling to reduce perceived latency).
- Stops tailing once `SessionCapture.is_active()` returns False and no new bytes have appeared for 2 seconds.
- No WebSocket dependency; standard SSE (`text/event-stream`).

Error handling:
- CLI subprocess non-zero exit: return `{ok: false, error: stderr_content}` with HTTP 200 (not 500); the CLI already communicates failure semantics through exit codes and stderr.
- Missing artifacts (e.g., no log file yet): return `{content: ""}` rather than 404 for optional artifacts.
- Invalid artifact name in spec chat: HTTP 400.

Constraints enforced:
- Backend never writes `.aiw/**` or locked artifacts directly.
- All state mutations go through AIW CLI subprocess.
- Spec chat refused when artifact is not in DRAFT state.
- Server binds to localhost only (127.0.0.1), not 0.0.0.0.

Non-goals:
- No frontend serving (done in TASK-042).
- No authentication or TLS.
- No canvas CLI command (`aiw canvas`) (done in TASK-042).
- No modification to spec_phase.py, executor.py, or any existing module.

Acceptance criteria (measurable):
1. `GET /api/state` returns current workflow state parsed from `workflow_state.json`.
2. `GET /api/tasks` returns task list with status correctly derived from COMPLETED.md.
3. `GET /api/dag` returns valid parsed DAG structure.
4. `POST /api/go/{task_id}` shells out to `aiw go` and returns stdout/stderr.
5. `POST /api/spec/chat/prd` invokes SpecDraftSession with prd system prompt and returns reply + updated document.
6. `POST /api/spec/chat/prd` returns HTTP 409 when state is not PRD_DRAFT.
7. `GET /api/events` streams `state_changed` event when `workflow_state.json` changes (verified with mock).
8. `GET /api/sessions/{run_id}` returns `{content: "", active: false}` when log file absent.
9. `GET /api/sessions/{run_id}` returns log file content and `active: true` when session is running (verified with mock SessionCapture).
10. `GET /api/events` emits `session_output` SSE events with correct `run_id` and `chunk` as session log file grows (verified with mock file writes).
11. No endpoint writes to `.aiw/` or `docs/` directly (verified by test asserting no file writes outside subprocess).
12. Server binds to 127.0.0.1 only.

Tests / checks required:
- `pytest tests/test_canvas_server.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Server logs each request to stdout (uvicorn default).
- No AIW trace events emitted by canvas server itself.

Rollback plan:
- `git checkout` to pre-task baseline.
