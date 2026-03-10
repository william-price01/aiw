# PRD: AIW (AI Workflow) – Local AI Coding Orchestrator

## 1. Problem Statement

Brute-force coding with chat-based AI tools (e.g., Claude Code) is fast but inefficient:

- Context resets waste time.
- Iterations are unstructured and difficult to reproduce.
- There are no enforced guardrails (write scope, bounded loops).
- Subagent reasoning is opaque.
- Costs are unpredictable.
- Artifacts (PRD, SDD, tasks) are inconsistent.

AIW is a **spec-locked, deterministic AI execution engine governed by an explicit workflow state machine**. It must match or exceed Claude Code in speed while adding structure, reproducibility, visibility, and bounded execution.

AIW is artifact-driven. It executes work strictly from versioned artifacts (PRD, SDD, constraints, ADRs, tasks). It does not function as a free-form chat wrapper.

It is not a SaaS product. It runs locally inside a git repository.

---

## 2. Target Users

**Primary User:**  
- Single advanced developer (power user).
- Comfortable with CLI.
- Values speed over ceremony.
- Wants deterministic artifacts and tight iteration loops.
- Optimizes for cost and execution velocity.

No multi-user support is required.

---

## 3. User Stories

1) As a developer, I want AIW to enforce hard execution boundaries so AI does not modify forbidden files or expand scope silently.

2) As a developer, I want deterministic, inspectable artifacts so I can reproduce work and understand what happened without trusting the model’s narrative.

3) As a developer, I want bounded iteration loops so tasks terminate deterministically (PASS or BLOCKED) without infinite refinement.

4) As a developer, I want per-task logs and structured run traces so I can audit changes and failures.

---

## 4. Scope (In)

AIW MVP must support:

- A spec-locked workflow (PRD → SDD → ADRs → constraints → planning → execution).
- Explicit workflow state machine enforcement via `.aiw/workflow_state.json`.
- Constraints enforcement:
  - write scope validation
  - diff size thresholds
  - required quality gates
  - layer import boundaries
- A bounded execution engine:
  - one selected task at a time
  - Coder session
  - deterministic termination
- Deterministic decomposition:
  - generate `docs/tasks/DAG.md` + `docs/tasks/DAG.yml`
  - generate `docs/tasks/TASK-###.md` task specs
- Deterministic logging:
  - per-task capsule log
  - task completion tracker (`docs/tasks/COMPLETED.md`)
  - structured JSONL run trace

User-authored authoritative artifacts:

- `docs/prd.md`
- `docs/sdd.md`
- `docs/constraints.yml`
- `docs/adrs/**`
- `docs/tasks/**`

Reports must live in:

- `docs/reports/`

Change requests must live in:

- `docs/requests/CHANGE_REQUEST.md`

---

## 5. Workflow State Machine (Authoritative)

AIW is governed by an explicit state machine stored in:

`.aiw/workflow_state.json`

### 5.1 States

- `INIT`
- `PRD_DRAFT` → `PRD_APPROVED`
- `SDD_DRAFT` → `SDD_APPROVED`
- `ADRS_DRAFT` → `ADRS_APPROVED`
- `CONSTRAINTS_DRAFT` → `CONSTRAINTS_APPROVED`
- `PLANNED`
- `EXECUTING`
- `BLOCKED`

---

### 5.2 Command Allowance by State

- `INIT`
  - `aiw init`
  - `aiw prd`

- `PRD_DRAFT`
  - edit PRD
  - approve PRD → `PRD_APPROVED`

- `PRD_APPROVED`
  - `aiw sdd`

- `SDD_DRAFT`
  - edit SDD
  - approve SDD → `SDD_APPROVED`

- `SDD_APPROVED`
  - `aiw adrs`

- `ADRS_DRAFT`
  - edit ADRs
  - approve ADRs → `ADRS_APPROVED`

- `ADRS_APPROVED`
  - `aiw constraints`

- `CONSTRAINTS_DRAFT`
  - edit constraints
  - approve constraints → `CONSTRAINTS_APPROVED`

- `CONSTRAINTS_APPROVED`
  - `aiw decompose` (ONLY allowed from `CONSTRAINTS_APPROVED`)

- `PLANNED`
  - manual task selection
  - `aiw go TASK-###` (ONLY allowed from `PLANNED`)

- `EXECUTING`
  - `aiw undo`
  - `aiw reset TASK-###`

- `BLOCKED`
  - manual resolution required
  - optional change request

Invalid commands in a given state fail deterministically.

---

### 5.3 Locking Rules

Locks apply **after** approval states.

- `docs/prd.md` immutable after `PRD_APPROVED`.
- `docs/sdd.md` immutable after `SDD_APPROVED`.
- `docs/adrs/**` immutable after `ADRS_APPROVED`.
- `docs/constraints.yml` immutable after `CONSTRAINTS_APPROVED`.
- During `EXECUTING`, planning artifacts are immutable:
  - `docs/tasks/DAG.md`
  - `docs/tasks/DAG.yml`
  - `docs/tasks/TASK-???.md`
- During `EXECUTING`, `docs/tasks/COMPLETED.md` is writable in append-only mode to record completed tasks.

Silent edits to locked artifacts are prohibited.

---

### 5.4 Change Request Mechanism

If downstream work requires upstream modification:

- Create `docs/requests/CHANGE_REQUEST.md`.
- Specify:
  - target artifact
  - reason
  - impact
- Locked documents may only be modified after:
  - explicit change request resolution
  - re-approval transition

State transitions reflect re-approval.

---

### 5.5 AI Mediation Across All Phases

- All phases (PRD, SDD, ADRs, constraints, decompose, execution) may be AI-assisted.
- The state machine enforces **structure and gating**, not authorship.
- Spec-phase drafting applies to the DRAFT states: `PRD_DRAFT`, `SDD_DRAFT`, `ADRS_DRAFT`, and `CONSTRAINTS_DRAFT`.
- In a DRAFT state, the human and AI may iterate conversationally on the active artifact across multiple turns until the human explicitly approves.
- During spec drafting, the AI may modify only the artifact mapped to the active DRAFT state:
  - `PRD_DRAFT` → `docs/prd.md`
  - `SDD_DRAFT` → `docs/sdd.md`
  - `ADRS_DRAFT` → `docs/adrs/**`
  - `CONSTRAINTS_DRAFT` → `docs/constraints.yml`
- Approval is human-driven only. There is no automatic approval and no automatic transition to the next phase.
- `aiw decompose` is AI-assisted but is not a conversational DRAFT state; it is a deterministic planning command allowed only from `CONSTRAINTS_APPROVED`.
- Execution-phase AI uses a single bounded Coder session under strict write-scope enforcement.

## 6. Task Selection vs Task Execution

AIW separates:

- **Task Selection:** Which `TASK-###` to execute.
- **Task Execution:** How execution proceeds (bounded patch → validate → test → fix loop).

MVP task selection is manual:

- user selects the task file in `docs/tasks/`
- user runs:
  - `aiw go TASK-###`

Execution engine must not depend on how selection happened.

Future extensions may add deterministic selection (e.g., DAG-based), but that is out of scope.

---

## 7. Coding Loop (Core)

### 7.1 Overview

The execution loop is strictly bounded:

- One selected task per run.
- One Coder session per task run. No retries.
- Deterministic termination:
  - PASS → `PLANNED`
  - FAIL → `BLOCKED`

No background scheduler.
No daemon.
No concurrency.

---

### 7.2 Execution Flow

1. Validate state (`PLANNED` required).
2. Validate constraints (see below).
3. Transition to `EXECUTING`.
4. Spawn Coder session.
5. Apply patch.
6. Run deterministic local tests.
7. If tests PASS:
   - Update task log.
   - Append task completion record to `docs/tasks/COMPLETED.md`.
   - Transition to `PLANNED`.
   - Terminate.
8. If tests FAIL:
   - Generate `docs/reports/TASK-###_blocker_report.md`.
   - Update task log.
   - Transition to `BLOCKED`.
   - Terminate.

Agent terminates on PASS or BLOCKED. No retries within a single run.

---

### 7.3 Constraints Finalization Gate

`docs/constraints.yml` is part of the spec-locked contract.

Before `aiw decompose` or `aiw go`:

- Required execution gates (e.g., `test_command`) must be set.
- Placeholders or unset required fields cause deterministic refusal.
- Partial execution is not allowed if constraints are invalid.

AIW refuses execution if constraints are incomplete.

---

### 7.4 Deterministic Artifacts (Execution)

Execution artifacts are authoritative, deterministic, and append-only where applicable:

- Task spec: `docs/tasks/TASK-###.md`
- Task capsule log (append-only): `docs/tasks/TASK-###.log.md`
- Task completion tracker (append-only): `docs/tasks/COMPLETED.md`
- Structured run trace: `.aiw/runs/run-<timestamp>.jsonl`
- Workflow state: `.aiw/workflow_state.json`

Task capsule log contains:

- chosen task
- constraints snapshot hash
- applied diffs summaries per iteration
- test results per iteration
- PASS or BLOCKED termination

Task completion tracker contains one append-only record per PASSed task run with task ID, run ID, completion timestamp, and result.

Git diff is the source of truth for code changes.

---

### 7.5 Guardrails

- Write-scope enforced per task.
- Cross-task edits rejected.
- Diff size threshold enforced.
- Max iteration bound (default 3).
- Max token/cost bound.
- Max runtime bound.
- If a task is detected as too large to complete within bounded iterations, AIW generates `docs/reports/TASK-###_followup_tasks.md` with proposed smaller tasks and transitions to `BLOCKED` instead of thrashing or expanding scope mid-run. If the correct fix is to expand scope, AIW emits `docs/reports/TASK-###_scope_expansion_request.md` and transitions to `BLOCKED`.

---

### 7.6 Observability

- Structured run log:
  - `.aiw/runs/run-<timestamp>.jsonl`
- Required trace events:
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

---

## 8. Non-Goals (Out of Scope)

- Automatic DAG execution
- Background scheduler / daemon
- Concurrency / parallel agents
- Multi-user coordination
- Cloud execution
- Autonomous task discovery beyond declared DAG
- Fine-grained IDE plugins

---

## 9. Acceptance Criteria (Measurable)

MVP is complete when:

- State machine enforces workflow gating deterministically.
- `aiw decompose` is refused unless in `CONSTRAINTS_APPROVED`.
- `aiw go TASK-###` is refused unless in `PLANNED`.
- Locked artifacts cannot be modified without change request + re-approval.
- Execution loop terminates deterministically:
  - PASS → `PLANNED`
  - exhaustion → `BLOCKED`
- Write scope and diff thresholds are enforced.
- Task log and run trace are generated per run.
- Completed tasks are recorded in `docs/tasks/COMPLETED.md` on PASS.

---

## 10. Technical Assumptions

- Runs in a git repo.
- Python 3.10+ available.
- Codex CLI integration available locally.
- Test command is deterministic and local.

---

## 11. Risks

- Incomplete constraints lead to brittle execution.
- AI drift without strict scope validation.
- User frustration if state gating is unclear.

---

## 12. De-risk Strategy

- Enforce hard constraints gate before decompose/go.
- Enforce strict write scope and diff thresholds.
- Deterministic crash recovery:
  - stale EXECUTING → BLOCKED on startup.

---

## 13. MVP Milestones

1) State machine + artifact locking
2) Constraints gate enforcement
3) Deterministic decompose outputs
4) Bounded execution engine (Coder session)
5) Logs + observability
6) CLI/TUI polish

---

## 14. DAG Executor (`aiw run`)

### 14.1 Overview

`aiw run` is an autonomous execution command that walks the task DAG in topological order, parallelizes independent tasks where possible, and only interrupts the human on BLOCKED or when a change request is required. During a clean run, the human never needs to manually dispatch individual tasks.

`aiw run` is available from `PLANNED` state only.

### 14.2 Behavior

1. Load `docs/tasks/DAG.yml` and compute topological order.
2. Identify parallelizable layers (tasks with no unresolved interdependencies).
3. For each task layer (innermost dependency-safe set):
   - Invoke the existing `aiw go TASK-###` execution loop per task.
   - Tasks within the same parallelizable layer may execute concurrently.
   - Wait for all tasks in a layer to complete before advancing to the next layer.
4. On task PASS: mark complete, advance DAG state.
5. On task BLOCKED:
   - Pause the entire run.
   - Surface the blocker report to the operator.
   - Wait for explicit human resolution (`aiw run --resume` or manual `aiw go` after resolving).
   - Do not proceed with other tasks that depend on the blocked task.
   - Tasks in the current layer without dependency on the blocked task may continue to completion.
6. On completion of all tasks: transition to a terminal run-complete state and report summary.

### 14.3 State Machine

- `aiw run` is only allowed from `PLANNED`.
- Individual `aiw go` invocations within the run follow all existing execution-phase state machine rules.
- Between task completions, state remains `PLANNED` to preserve existing invariants.
- The DAG executor does not introduce new workflow states.

### 14.4 Concurrency Model

Parallelism is layer-scoped only. Tasks within the same DAG layer with no mutual file-scope collision may execute in parallel. File-scope collision detection is required before launching parallel tasks in the same layer.

No task may execute before all its declared dependencies have PASSed.

### 14.5 Non-Goals

- No autonomous DAG task discovery beyond `DAG.yml`.
- No dynamic re-decomposition during a run.
- Parallel execution across layers is not permitted.

---

## 15. Canvas (Control Plane Interface)

### 15.1 Overview

Canvas is a local web-based control plane for AIW. It is the primary interface for the full AIW lifecycle — from initial spec drafting through autonomous execution — for operators who prefer a visual interface over raw CLI.

Canvas does not replace the CLI. The AIW CLI remains the authoritative command surface. Canvas drives the CLI; it never writes state directly.

### 15.2 Spec Mode

In Spec Mode, the iterative AI-assisted spec development flow defined in §5.5 and SDD §4.1 is conducted inside the canvas. The canvas is the UI surface for that process — not a separate tool, not a terminal. The same state machine rules apply: entering a DRAFT state establishes one active editable artifact; iteration continues until the human explicitly approves; approval is human-driven only.

Each spec artifact (PRD, SDD, ADRs, constraints) has a dedicated panel with:
- A chat interface for AI-assisted drafting.
- A live document view showing the current artifact content.
- An approve button that triggers the corresponding `aiw approve-*` command when the human is ready.
- Locked artifacts are rendered read-only.

### 15.3 Execution Mode

Once the project reaches `PLANNED` state, the canvas switches to Execution Mode:

- The full task DAG is rendered as a live visual graph. Nodes are colored by state: pending, executing, passed, blocked.
- The operator may trigger `aiw run` from the canvas to start autonomous execution.
- Active agent sessions are visible in real time via trace event streaming.
- Blocked nodes surface the blocker report inline. The operator can inspect the blocker, resolve it, and resume execution without leaving the canvas.
- Any node is clickable to view: task spec, capsule log, trace events, and live coding session output.
- Change requests can be submitted from the canvas, which triggers `aiw request-change`.

### 15.3.1 Session Visibility

Coding sessions (Coder) are observable from the canvas in real time. Clicking an executing or completed task node opens a session pane with two views:

**Terminal view**: Raw streaming output from the Codex CLI process, rendered as a terminal emulator in the browser. During an active session, output streams live. After session completion, the full session log is available for replay.

**Structured summary view**: Per-iteration panels showing the prompt context (task spec excerpt), the resulting patch (git diff), and the test output. This view is assembled from existing artifacts — task spec, git diff, capsule log — and requires no additional capture.

Session logs are persisted to `.aiw/runs/` alongside the JSONL trace and are available for inspection after the session ends. The session pipe is designed to support interactive input in a future extension; for MVP it is read-only.

### 15.4 Constraints

- Canvas never bypasses the AIW state machine.
- All mutations go through the AIW CLI or AIW Python API surface. The canvas backend does not write `.aiw/workflow_state.json` or any locked artifact directly.
- Canvas is local-only. No external services, no authentication, no cloud connectivity.
- Canvas is launched with `aiw canvas` and serves on localhost.

### 15.5 Non-Goals

- No multi-user support.
- No cloud hosting.
- No mobile interface.
- Canvas does not replace the CLI for scripted or CI usage.
- Interactive input to coding sessions (read-only session visibility for MVP; interactive path is forward-compatible but not implemented).
