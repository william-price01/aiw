# SDD: aiw (AI Workflow) — Local AI Coding Orchestrator

This SDD clarifies execution semantics and hardens the workflow contract.

It does **not** redesign AIW.
It does **not** introduce new subsystems.
It does **not** add autonomous DAG execution into MVP.

Key clarifications included:

* Task Selection vs Task Execution boundary
* Codex session model (single Coder session)
* Crash / stale `EXECUTING` recovery

---

# 1. System Overview

AIW is an artifact-driven execution engine governed by a strict workflow state machine.

It is not a conversational wrapper.
It executes bounded work from explicit task artifacts.

Core principles:

* Explicit workflow gating (hard state enforcement)
* Artifact-locked specs (PRD / SDD / ADRs / constraints)
* Deterministic planning outputs (DAG + tasks)
* Bounded execution loop (single Coder session)
* Deterministic termination (`PASS` or `BLOCKED`)

---

# 2. Authoritative `aiw init` Scaffold

Creates the minimum internal tool state directory:

* `.aiw/`
* `.aiw/workflow_state.json`
* `.aiw/runs/`

---

## 2.1 User-Facing Artifacts (Editable by User)

User-authored artifacts live in `docs/`:

* `docs/prd.md`
* `docs/sdd.md`
* `docs/constraints.yml`
* `docs/adrs/`
* `docs/tasks/`
* `docs/tasks/COMPLETED.md` (append-only task completion tracker)

Reports live in:

* `docs/reports/`

Change requests live in:

* `docs/requests/CHANGE_REQUEST.md`

---

## 2.2 Tool-Internal State (Not User-Authored)

Internal state is owned by AIW:

* `.aiw/`
* `.aiw/workflow_state.json`
* `.aiw/runs/run-<timestamp>.jsonl`

Coding agents must **not** write to `.aiw/**`.

---

# 3. Task Selection vs Task Execution Boundary (Conceptual Contract)

The system MUST separate:

* **Task Selection** — which TASK is chosen
* **Task Execution** — how the execution loop runs

---

## 3.1 Task Selection (Which TASK to run)

MVP task selection is manual:

* User chooses a `docs/tasks/TASK-###.md`
* User runs: `aiw go TASK-###`

Task selection is not part of the execution engine.

Future selection mechanisms may exist (e.g., deterministic DAG selection), but in MVP there is:

* No scheduler
* No daemon
* No concurrency
* No autonomous chaining

---

## 3.2 Task Execution (How a TASK runs)

Task execution is a deterministic bounded loop:

* Patch
* Validate
* Test
* Fix (optional)
* Terminate (`PASS` or `BLOCKED`)

The execution engine MUST be independent of the selection mechanism.

No orchestration threads.
No autonomous task chaining in MVP.

The boundary is conceptual only. No new component is introduced.

---

# 4. AI Session Model (Global)

AIW permits AI assistance across both spec-phase and execution-phase, with distinct contracts.

---

## 4.1 Spec-Phase AI (Artifact Authoring / Revision)

Applies to:

* `PRD_DRAFT`
* `SDD_DRAFT`
* `ADRS_DRAFT`
* `CONSTRAINTS_DRAFT`

Rules:

* Entering a spec-phase DRAFT state establishes exactly one active editable artifact:
  * `PRD_DRAFT` → `docs/prd.md`
  * `SDD_DRAFT` → `docs/sdd.md`
  * `ADRS_DRAFT` → `docs/adrs/**`
  * `CONSTRAINTS_DRAFT` → `docs/constraints.yml`
* Spec-phase drafting is conversational and iterative.
* The human and AI may revise the active artifact across multiple turns.
* Iteration continues until the human explicitly approves the active artifact.
* The AI must not modify artifacts outside the active draft scope.
* There is no automatic approval.
* There is no automatic transition to the next phase.
* Spec-phase drafting does not use the execution-phase bounded patch → validate → test → fix loop.

---

## 4.2 Execution-Phase AI (Task Runs)

Applies to:

* `aiw go TASK-###`

Execution uses a **single Coder session** with enforced write scope. One session per run. PASS or BLOCKED. No retries.

The execution engine is independent of the task selection mechanism.

---

# 5. Global Workflow State Machine

Stored in:

```
.aiw/workflow_state.json
```

## States

```
INIT
PRD_DRAFT
PRD_APPROVED
SDD_DRAFT
SDD_APPROVED
ADRS_DRAFT
ADRS_APPROVED
CONSTRAINTS_DRAFT
CONSTRAINTS_APPROVED
PLANNED
EXECUTING
BLOCKED
```

---

## 5.1 CONSTRAINTS_APPROVED → PLANNED Transition

Under `CONSTRAINTS_APPROVED`:

Command:

```
aiw decompose
```

On success, outputs written:

* `docs/tasks/DAG.md`
* `docs/tasks/DAG.yml`
* `docs/tasks/TASK-###.md`

Transition:

```
CONSTRAINTS_APPROVED → PLANNED
```

Decompose must not partially write artifacts. Failure aborts deterministically.

---

## 5.2 EXECUTING Entry Semantics

On entering `EXECUTING`:

* A `run_id` (UUID) is generated.
* Written to:

  * `.aiw/workflow_state.json`
  * JSONL trace header.
* Pre-task baseline checkpoint created.
* State updated atomically.

---

## 5.3 Crash / Stale EXECUTING Determinism

On startup:

If `.aiw/workflow_state.json` shows:

```
state = EXECUTING
```

Then:

* System MUST NOT resume silently.
* State transitions deterministically to:

```
BLOCKED
```

No automatic recovery.
User must manually resolve and return to `PLANNED` before re-running.

No partial execution resumes are permitted.

---

# 6. Locking Rules (Explicit)

Locks apply after approval states and are enforced via Git diff validation before patch application.

After approval:

* `docs/prd.md` locked after `PRD_APPROVED`
* `docs/sdd.md` locked after `SDD_APPROVED`
* `docs/adrs/**` locked after `ADRS_APPROVED`
* `docs/constraints.yml` locked after `CONSTRAINTS_APPROVED`

During `EXECUTING`, planning artifacts are immutable:

* `docs/tasks/DAG.md`
* `docs/tasks/DAG.yml`
* `docs/tasks/TASK-???.md`
* `docs/tasks/COMPLETED.md` is explicitly writable in append-only mode for completion marks.

Any attempt to modify locked artifacts causes:

* Immediate hard-fail
* Revert to last checkpoint
* Emit `lock_violation_hard_fail`
* Abort run

Workflow state remains unchanged unless explicitly transitioned.

---

# 7. Deterministic Constraints Gate (Preflight)

Before:

* `aiw decompose`
* `aiw go`

AIW MUST validate:

* `docs/constraints.yml` exists
* Required execution gates configured:

  * `test_command`
  * Scope rules
* Repository accessible via Git

If validation fails:

* Command aborts immediately
* No partial artifacts written
* Emit trace event: `constraint_validation_failed`

---

# 8. Task Lint Preflight Gate

Before execution:

* `docs/tasks/TASK-###.md` must exist.
* Required fields:

  * Acceptance criteria
  * Tests to run
  * File scope allowlist
  * Non-goals
* Scope consistent with `docs/constraints.yml`.

If lint fails:

* Execution refused
* Emit `task_lint_failed`
* No patch applied

---

# 9. Coding Loop State Machine (EXECUTING)

Within `EXECUTING`:

1. Coder session produces patch.
2. AIW validates patch:

   * Write scope
   * Locked artifact diffs
   * Diff size thresholds
3. If valid:

   * Apply patch
4. Run deterministic tests.

5. If PASS:
   * Log result
   * Append completion record to `docs/tasks/COMPLETED.md`
   * Emit `task_marked_complete`
   * Transition to `PLANNED`

6. If FAIL:

   * Emit `test_run_failed`
   * Emit:

     * `docs/reports/TASK-###_blocker_report.md`
     * `docs/reports/TASK-###_followup_tasks.md` (if needed)
     * `docs/reports/TASK-###_scope_expansion_request.md` (if needed)
   * Transition to `BLOCKED`

No retries. No background retries. No parallel agents.

---

# 10. Codex Session Model (Single Coder Session)

Each `aiw go TASK-###` run permits exactly one **Coder** session. There is no Fixer session.
See ADR-013 for rationale.

## 10.1 Coder Session

* One session per run. No retries.
* Task-scoped file allowlist enforced.
* Produces bounded patch.
* On test failure: task transitions directly to BLOCKED.

Strict limits:

* No additional model calls beyond the single Coder session.
* No cross-task edits.

---

# 11. Constraint Enforcement

Constraints enforced via deterministic gates:

* Write scope validation
* Locked artifact diff checks
* Diff size thresholds
* Layering / import boundaries
* Required test command presence
* Forbidden path checks

Quality gate failures MUST emit:

```
quality_gate_failed
```

---

## 11.1 Core Required Trace Events

Core required trace events are:

- state_transition
- constraint_validation
- scope_validation
- diff_threshold_check
- test_run_started
- test_run_failed
- test_run_passed
- blocked
- run_complete
- task_marked_complete
- quality_gate_failed
- lock_violation_hard_fail

Other sections may define additional conditional emitted events for specific failure paths. Those do not change the core required trace-event set unless they are also added to `docs/prd.md` and `docs/constraints.yml`.

# 12. Backend Integration

AIW integrates with Codex CLI in a bounded manner appropriate to each phase:

* Spec-phase draft commands may invoke AI repeatedly across the active DRAFT session, but only within the active artifact scope defined by workflow state.
* `aiw decompose` may use one bounded AI invocation to produce deterministic planning outputs.
* `aiw go TASK-###` uses a single Coder session. No Fixer session.
* No streaming orchestration threads
* No autonomous agent loops

Codex output is treated as a proposed artifact revision or patch, depending on phase.
Git diff is authoritative for code changes.
---

# 13. Checkpointing / Undo / Reset

## Checkpoints

Created:

* Before `EXECUTING` entry
* After each applied patch

Implemented via Git commits or deterministic refs.

## `aiw undo`

Reverts most recent checkpoint for current run.

## `aiw reset TASK-###`

Resets working tree to baseline for selected task run.

Both operations are deterministic.

---

# 14. BLOCKED Retry Semantics

When in `BLOCKED`:

* No automatic retries
* User must resolve:

  * Missing constraints
  * Failing tests
  * Scope mismatch
  * Environment mismatch

Retry requires:

* Returning to `PLANNED`
* Re-running `aiw go TASK-###`

---

# 15. TUI Rendering Model

TUI derives strictly from:

* Workflow state
* Task artifacts
* Run trace events

No speculative UI state.

---

# 16. File Structure

```
docs/
  prd.md
  sdd.md
  constraints.yml
  adrs/
  tasks/
    DAG.md
    DAG.yml
    TASK-001.md
    TASK-001.log.md
  reports/
    TASK-001_blocker_report.md
    TASK-001_scope_expansion_request.md
    TASK-001_followup_tasks.md
  requests/
    CHANGE_REQUEST.md
.aiw/
  agents/
  workflow_state.json
  runs/
    run-<timestamp>.jsonl
```

---

# 17. Architecture Decision Records (Updated Clarifications)

## ADR-009: Execution Engine Isolation

Task execution engine must not depend on task selection mechanism.

## ADR-010 → ADR-013: Single Coder Session

ADR-010 (Two-Session Codex Model) is superseded by ADR-013.
Each task run permits exactly one Coder session. No Fixer. No iteration cap.

## ADR-011: Deterministic Crash Handling

Stale `EXECUTING` state transitions to `BLOCKED` on startup.

## ADR-012: Hard Constraints Gate

`docs/constraints.yml` and execution gates must validate before `decompose` or `go`.

---

# 18. DAG Executor (`aiw run`)

## 18.1 Overview

The DAG executor implements `aiw run`, which autonomously walks `docs/tasks/DAG.yml` in topological order, parallelizes independent layers, and invokes the existing bounded execution loop per task. It is the implementation of PRD §14.

## 18.2 DAG Loading and Topological Resolution

On invocation, the DAG executor:

1. Reads `docs/tasks/DAG.yml` and constructs a dependency graph.
2. Computes topological order using Kahn's algorithm or equivalent.
3. Identifies parallelizable layer sets: tasks whose declared `depends_on` entries are all already PASSED.
4. Determines which tasks have already completed by reading `docs/tasks/COMPLETED.md`.
5. Builds the initial ready set: tasks with all dependencies satisfied and not yet PASSED.

## 18.3 Execution Model

The DAG executor drives the existing `execute_task()` function (TASK-015/027) per task. No new execution loop is introduced. The executor is a scheduling wrapper only.

For each ready layer:
- If tasks are parallelizable (no mutual file-scope overlap), launch them concurrently using `concurrent.futures.ThreadPoolExecutor` or `asyncio`.
- File-scope collision between two tasks in the same layer forces them to be serialized.
- Await completion of all tasks in the current layer before computing the next ready set.

On task PASS:
- Mark the task complete in `docs/tasks/COMPLETED.md` (via the existing completion mechanism).
- Recompute the ready set.

On task BLOCKED:
- Pause graph advancement.
- Emit `dag_task_blocked` trace event with task ID and blocker report path.
- Print the blocker summary to stdout.
- Halt only the tasks that depend (directly or transitively) on the blocked task.
- Independent tasks in the current layer that are already running may complete.
- Wait for operator resolution. Operator resolves via `aiw run --resume` after manually clearing the BLOCKED state via `aiw go TASK-###` retry or change request.

## 18.4 State Machine Implications

- `aiw run` is permitted only from `PLANNED`.
- Between individual task completions, workflow state returns to `PLANNED` (per existing EXECUTING → PLANNED success transition).
- The DAG executor does not hold a persistent EXECUTING state across multiple task runs.
- There are no new workflow states.
- `aiw run --resume` re-enters the DAG executor from PLANNED with the updated completion set, skipping already-PASSED tasks.

## 18.5 File-Scope Collision Detection

Before launching two tasks in parallel, the executor intersects their `filescope` allowlists from `DAG.yml`. If any overlap exists, the tasks are serialized within the layer. This is a pre-launch check only; no runtime locking is required.

## 18.6 Observability

Required additional trace events for DAG executor:

- `dag_run_started`: emitted when `aiw run` begins, includes total task count and layer count.
- `dag_layer_started`: emitted when a new layer begins execution, includes task IDs in layer.
- `dag_task_blocked`: emitted when a task transitions to BLOCKED, includes task ID.
- `dag_run_complete`: emitted on successful completion of all tasks, includes summary.
- `dag_run_paused`: emitted when execution pauses due to a BLOCKED task.

---

# 19. Canvas Architecture

## 19.1 Overview

Canvas is a local web-based control plane implemented as a thin Python HTTP server (FastAPI) serving a React frontend. It wraps the AIW CLI and AI session model. All state mutations go through the CLI. The backend never writes AIW state directly.

## 19.2 Backend — API Server

The backend is a FastAPI application that exposes:

**Read endpoints:**
- `GET /api/state` — reads and returns `.aiw/workflow_state.json`.
- `GET /api/tasks` — lists `docs/tasks/TASK-###.md` files with parsed metadata.
- `GET /api/tasks/{task_id}` — returns full task spec content.
- `GET /api/tasks/{task_id}/log` — returns capsule log content.
- `GET /api/dag` — returns parsed `docs/tasks/DAG.yml`.
- `GET /api/runs` — lists available JSONL run trace files.
- `GET /api/runs/{run_id}` — returns parsed trace events for a run.
- `GET /api/completed` — returns parsed `docs/tasks/COMPLETED.md`.
- `GET /api/sessions/{run_id}/{session_type}` — returns persisted session log content for `session_type` ∈ `{coder, fixer}`. Returns `{run_id, session_type, content: str, active: bool}`. `content` is the full raw log captured so far; `active` is true if the session process is still running.

**Write endpoints (shell out to AIW CLI only):**
- `POST /api/run` — invokes `aiw run`.
- `POST /api/go/{task_id}` — invokes `aiw go TASK-###`.
- `POST /api/approve/{artifact}` — invokes `aiw approve-prd`, `aiw approve-sdd`, etc.
- `POST /api/request-change` — invokes `aiw request-change`.
- `POST /api/command` — generic CLI command passthrough for other commands.

The backend uses `subprocess.run` to shell out to the AIW CLI. It captures stdout/stderr and returns structured JSON responses. No direct writes to `.aiw/` or `docs/`.

**Spec chat endpoints:**
- `POST /api/spec/chat/{artifact}` — accepts `{message: str, document: str}`, invokes a bounded AI session using the existing spec-phase system prompts from `spec_phase.py`, returns `{reply: str, updated_document: str}`.
- One endpoint per artifact: `prd`, `sdd`, `adrs`, `constraints`.
- The AI session is non-persistent. Full document content and conversation history are passed in each request.
- The backend uses the same `SpecDraftSession` infrastructure already implemented in `aiw/orchestrator/spec_phase.py`.

**Live state push:**
- The backend exposes a `GET /api/events` SSE (Server-Sent Events) endpoint.
- It polls `.aiw/workflow_state.json` and the active JSONL run trace file at 1-second intervals.
- State changes and new trace events are pushed to connected frontend clients via SSE.
- The SSE endpoint also tails the active session log file (`session-<run_id>-coder.log`) when it exists and is still being written. New bytes are pushed as `session_output` events with payload `{run_id, session_type, chunk: str}`.
- No WebSocket dependency.

## 19.2.1 Session Capture Architecture

The Coder session is captured via a pty-based subprocess wrapper (`SessionCapture`), implemented in TASK-043. The executor calls `SessionCapture` instead of spawning Codex directly. This is the only change to the executor's subprocess invocation path.

**Session log files** are written to `.aiw/runs/` alongside the JSONL trace:
- `.aiw/runs/session-<run_id>-coder.log` — raw pty output from the Coder session.

Files are written append-only during the session and remain for post-session inspection.

**Pty rationale**: Codex CLI is an interactive process. A pty (pseudo-terminal) is required to avoid output buffering changes and ANSI suppression that occur when Codex detects it is not attached to a terminal. Using a pty also preserves the pipe contract for future interactive input (stdin injection) without requiring architectural changes.

**`SessionCapture` contract**:
- Wraps a subprocess via `pty.openpty()` (or `pexpect`/`ptyprocess` for cross-platform compatibility).
- Streams pty output to two sinks simultaneously: the session log file (persisted) and an in-memory buffer (for SSE push).
- Exposes `stdout_iter()` async iterator for the SSE tail loop.
- Exposes `pid` for future stdin injection; write path is not implemented for MVP.
- On process exit: closes log file, marks session as inactive.

**Structured summary** in the canvas frontend is assembled read-only from existing artifacts (task spec, git diff from `git diff HEAD~1`, capsule log). No additional capture is required for this view.

## 19.3 Frontend — Canvas UI

The React frontend has two primary modes, determined by current workflow state:

**Spec Mode** (states: INIT through CONSTRAINTS_APPROVED, and DRAFT states):
- Left navigation lists spec artifacts: PRD, SDD, ADRs, Constraints.
- Each artifact opens a split view: chat panel on the left, live document on the right.
- Chat panel sends messages to `POST /api/spec/chat/{artifact}`.
- Document panel re-renders on each reply with the updated content.
- Approve button is enabled when the artifact is in its DRAFT state; triggers `POST /api/approve/{artifact}`.
- Locked artifacts render the document as read-only with no chat input.

**Execution Mode** (states: PLANNED, EXECUTING, BLOCKED):
- DAG graph rendered as a directed acyclic graph using a graph layout library (e.g., dagre).
- Node colors: gray (pending), blue (executing), green (passed), red (blocked).
- Node click opens a `TaskDetail` side panel with four tabs: Spec, Session, Capsule Log, Trace Events.
- `aiw run` button triggers `POST /api/run`.
- Blocked nodes show an inline blocker report with a resolve/retry action.
- Change request form triggers `POST /api/request-change`.
- Live updates via SSE subscription to `/api/events`.

**`TaskDetail` — Session tab (`SessionPane` component):**
- Two sub-tabs: **Terminal** and **Summary**.
- **Terminal sub-tab**: renders raw session log output using xterm.js (or equivalent terminal emulator). During an active session, subscribes to `session_output` SSE events and appends chunks in real time. For completed sessions, loads full log from `GET /api/sessions/{run_id}/coder`. Renders ANSI escape sequences correctly. Read-only: no input field rendered for MVP, but the xterm instance is initialized with `disableStdin: true` and the instance ref is exposed so the input path can be wired without component replacement.
- **Summary sub-tab**: single-pass summary panel showing: task spec excerpt, git diff summary (from trace event payloads), test output (from `test_run_failed` / `test_run_passed` trace events). Assembled read-only from existing artifacts.
- If no session log exists yet (task pending or just dispatched): shows "Waiting for session to start..."

**State-based mode switching:**
- The frontend subscribes to `/api/events` on mount.
- On state change event, re-evaluates which mode to render.
- Transition between modes is seamless and state-driven.

## 19.4 Canvas Launch (`aiw canvas`)

`aiw canvas` is a new CLI command that:
1. Validates the current directory is an AIW-initialized repo (`.aiw/` exists).
2. Starts the FastAPI server on `localhost:7842` (default, configurable).
3. Opens the default browser to `http://localhost:7842`.
4. Serves until interrupted (Ctrl-C).

The frontend is bundled as static assets and embedded in the Python package. No separate build step is required for end users.

## 19.5 Technology Constraints

- Backend: Python, FastAPI, uvicorn. No external AI API calls from backend except via the existing AIW session model.
- Frontend: React, plain CSS or Tailwind. No external UI component library dependencies beyond what can be bundled. xterm.js bundled for terminal rendering.
- Session capture: `ptyprocess` or `pexpect` for cross-platform pty management (Linux/macOS). Windows pty support is not required for MVP.
- Packaging: frontend static assets co-located with the Python package at `aiw/canvas/static/`.
- No external services. No authentication. No cloud connectivity.
- All AI interactions use the existing `SpecDraftSession` and Codex session infrastructure in AIW.
