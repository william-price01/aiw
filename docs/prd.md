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
  - Coder + optional Fixer sessions
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
- Spec-phase AI (PRD/SDD/ADRs/constraints) is single-pass and artifact-scoped (generate or revise the target artifact only).
- Execution-phase AI uses bounded iterative sessions (Coder + optional Fixer) under strict iteration and write-scope enforcement.

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
- One Coder session per task run.
- Optional Fixer session only after failed test run.
- Hard max iteration cap (default: 3).
- Deterministic termination:
  - PASS → `PLANNED`
  - exhaustion → `BLOCKED`

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
   - Spawn Fixer session.
   - Apply fix.
   - Re-run tests.
9. Stop after max N iterations (default: 3).
10. If still failing:
    - Generate `docs/reports/TASK-###_blocker_report.md`.
    - Update task log.
    - Transition to `BLOCKED`.

Agent terminates on PASS or BLOCKED.

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
  - fixer_spawned
  - iteration_exhausted
  - quality_gate_failed
  - blocked
  - run_complete

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
4) Bounded execution engine (Coder/Fixer)
5) Logs + observability
6) CLI/TUI polish
