## TASK-041: Canvas frontend

Type: IMPLEMENTATION
Depends_on: [TASK-040]

Objective:
Implement the React frontend for Canvas with two primary modes: Spec Mode for AI-assisted
spec drafting (one panel per artifact with chat + live document) and Execution Mode (live DAG
graph, task detail panel with session visibility, trace viewer, blocker surface, `aiw run`
trigger). Mode switching is state-driven. All data comes from the Canvas API server (TASK-040).
Session visibility includes a live terminal view (xterm.js) and a structured iteration summary.

Context (spec refs):
- PRD §15.2 (Spec Mode), §15.3 (Execution Mode), §15.4 (constraints)
- SDD §19.3 (Frontend)

Inputs:
- Canvas API server from TASK-040 (all `/api/*` endpoints)
- `GET /api/events` SSE stream for live updates

Outputs (artifacts/files created or changed):
- `aiw/canvas/frontend/` (full React application source)
- `aiw/canvas/frontend/package.json`
- `aiw/canvas/frontend/src/App.jsx`
- `aiw/canvas/frontend/src/components/SpecMode.jsx`
- `aiw/canvas/frontend/src/components/ArtifactPanel.jsx`
- `aiw/canvas/frontend/src/components/ExecutionMode.jsx`
- `aiw/canvas/frontend/src/components/DagGraph.jsx`
- `aiw/canvas/frontend/src/components/TaskDetail.jsx`
- `aiw/canvas/frontend/src/components/SessionPane.jsx`
- `aiw/canvas/frontend/src/components/TraceViewer.jsx`
- `aiw/canvas/frontend/src/components/BlockerPanel.jsx`
- `aiw/canvas/frontend/src/api.js`
- `tests/test_canvas_frontend_build.py`

File scope allowlist:
- aiw/canvas/frontend/**

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:

Mode switching:
- Frontend subscribes to `GET /api/events` on mount.
- On `state_changed` event: re-fetches `/api/state` and re-evaluates mode.
- States INIT through CONSTRAINTS_APPROVED (including all DRAFT states) → Spec Mode.
- States PLANNED, EXECUTING, BLOCKED → Execution Mode.

Spec Mode — `SpecMode` component:
- Left nav: PRD, SDD, ADRs, Constraints (tabs or sidebar).
- Each artifact tab renders `ArtifactPanel`.
- `ArtifactPanel` props: `{artifact, state, document, history}`.
- Split layout: chat panel (left 40%) + document panel (right 60%).
- Chat input sends `POST /api/spec/chat/{artifact}` with current `{message, document, history}`.
- On reply: update document panel with `updated_document`; append assistant reply to history.
- Approve button: enabled only when artifact is in DRAFT state; sends `POST /api/approve/{artifact}`.
- Locked artifact: document panel is read-only; chat input disabled; no approve button.
- Document panel renders markdown as formatted HTML (use a markdown renderer library).

Execution Mode — `ExecutionMode` component:
- Top action bar: `aiw run` button (sends `POST /api/run`); `aiw run --resume` button (sends `POST /api/run/resume`); disabled when not in PLANNED state.
- `DagGraph` component: renders DAG using fetched `/api/dag` and `/api/completed` data.
  - Node colors: gray=pending, blue=executing, green=passed, red=blocked.
  - Directed edges between dependent nodes.
  - Graph layout via dagre or equivalent.
  - Node click → open `TaskDetail` side panel.
- `TaskDetail` panel: tabbed interface with four tabs: **Spec**, **Session**, **Capsule Log**, **Trace Events**.
  - **Spec tab**: task spec markdown rendered as HTML (fetched from `GET /api/tasks/{task_id}`).
  - **Session tab**: `SessionPane` component (see below).
  - **Capsule Log tab**: capsule log markdown rendered as HTML (from `GET /api/tasks/{task_id}/log`).
  - **Trace Events tab**: `TraceViewer` component.
- `SessionPane` component:
  - Two sub-tabs: **Terminal** and **Summary**.
  - **Terminal sub-tab**:
    - Renders raw session output using xterm.js (`@xterm/xterm` package).
    - On mount: fetches `GET /api/sessions/{run_id}` and writes existing content to xterm instance.
    - Subscribes to `session_output` SSE events from `/api/events`; on each event matching `run_id`, calls `terminal.write(chunk)`.
    - xterm initialized with `disableStdin: true` for MVP. The xterm instance and its DOM element are exposed via a `ref` so a future `disableStdin: false` + stdin write path can be added without replacing the component.
    - Shows "Waiting for session to start..." when `content === ""` and `active === false`.
    - ANSI escape sequences rendered correctly by xterm (no stripping).
  - **Summary sub-tab**:
    - Single-pass summary panel assembled from existing artifacts.
    - Data fetched from: trace events (`test_run_started`, `test_run_failed`, `test_run_passed` from `GET /api/runs/{run_id}`), diff summary from trace event payloads.
    - Shows: session type (Coder), diff summary, test result (PASS/FAIL), test output excerpt.
    - Read-only; no new capture required.
    - Shows "No session data yet" when trace events are absent.
- `TraceViewer`: renders trace events from `/api/runs/{run_id}` as a scrollable timestamped list; auto-appends new events on `trace_event` SSE events.
- `BlockerPanel`: rendered inline on blocked nodes; shows blocker report content; includes `Resolve & Retry` button that sends `POST /api/go/{task_id}`.
- Change request form: opens on button click; fields for target artifact, reason, impact; submits `POST /api/request-change`.

`api.js`:
- Typed fetch wrappers for all `/api/*` endpoints.
- SSE connection manager (reconnects on disconnect).
- No direct file system or CLI access.

Build output:
- `npm run build` produces static assets in `aiw/canvas/frontend/dist/`.
- Build must succeed with no errors.
- `package.json` must include `@xterm/xterm` and `@xterm/addon-fit` as dependencies.
- `tests/test_canvas_frontend_build.py` runs `npm run build` in the frontend directory and asserts exit code 0 and `dist/index.html` exists.

Constraints enforced:
- No direct state writes from frontend (all mutations via API write endpoints).
- No external CDN dependencies at runtime (all dependencies bundled).
- Node.js required for build only; not for runtime serving.
- Frontend targets modern browsers only (no IE11 support required).

Non-goals:
- No mobile layout.
- No authentication.
- No server-side rendering.
- No frontend unit tests beyond build verification (full E2E testing deferred).
- No serving logic (done in TASK-042).

Acceptance criteria (measurable):
1. `npm run build` completes with exit code 0 in `aiw/canvas/frontend/`.
2. `dist/index.html` and bundled JS/CSS assets exist after build.
3. In Spec Mode: `ArtifactPanel` renders with chat input + document panel for each artifact.
4. Approve button disabled when artifact is not in DRAFT state (verified via component prop logic).
5. Locked artifact: chat input and approve button absent/disabled when state is post-approval.
6. In Execution Mode: `DagGraph` renders nodes with correct colors for each status.
7. `TaskDetail` panel opens on node click with four tabs: Spec, Session, Capsule Log, Trace Events.
8. Session tab shows `SessionPane` with Terminal and Summary sub-tabs.
9. Terminal sub-tab: xterm.js instance renders existing session log content on mount.
10. Terminal sub-tab: appends new chunks on `session_output` SSE events.
11. Terminal sub-tab: shows "Waiting for session to start..." when no session data exists.
12. xterm instance initialized with `disableStdin: true`; ref exposed on component for future input wiring.
13. Summary sub-tab: renders single-pass summary panel from trace event data.
14. `TraceViewer` renders trace events and appends new events on SSE push.
15. `BlockerPanel` rendered on blocked nodes with Resolve & Retry action.
16. Mode switching: frontend renders Spec Mode for DRAFT states, Execution Mode for PLANNED/EXECUTING/BLOCKED.
17. `tests/test_canvas_frontend_build.py` passes.

Tests / checks required:
- `pytest tests/test_canvas_frontend_build.py -q`
- `npm run build` (run from `aiw/canvas/frontend/`)
- `ruff check .` (Python files only)
- `mypy aiw tests` (Python files only)

Observability requirements:
- None. Frontend produces no AIW trace events.

Rollback plan:
- `git checkout` to pre-task baseline.
