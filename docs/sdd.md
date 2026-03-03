# SDD: aiw (AI Workflow) — Local AI Coding Orchestrator

This SDD clarifies execution semantics and hardens the workflow contract.

It does **not** redesign AIW.
It does **not** introduce new subsystems.
It does **not** add autonomous DAG execution into MVP.

Key clarifications included:

* Task Selection vs Task Execution boundary
* Codex session model (Coder + Fixer)
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
* Bounded execution loop (Coder + Fixer)
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

* PRD
* SDD
* ADRs
* constraints
* decomposition planning

Rules:

* Each spec-phase command may spawn **one bounded AI session**, scoped to the single target artifact (or deterministic output set).
* Spec-phase AI is **single-pass**.
* No bounded patch → test → fix loop.
* No iterative correction cycles.

---

## 4.2 Execution-Phase AI (Task Runs)

Applies to:

* `aiw go TASK-###`

Execution uses the **Coder + Fixer** model with strict iteration caps and enforced write scope.

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

Any attempt to modify locked artifacts causes:

* Immediate hard-fail
* Revert to last checkpoint
* Emit `LOCK_VIOLATION_HARD_FAIL`
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
  * `max_iterations`
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
   * Transition to `PLANNED`
6. If FAIL:

   * Spawn Fixer session
   * Apply fix
   * Re-run tests
7. Repeat up to `max_iterations` (default 3).
8. On exhaustion:

   * Emit:

     * `docs/reports/TASK-###_blocker_report.md`
     * `docs/reports/TASK-###_followup_tasks.md` (if needed)
     * `docs/reports/TASK-###_scope_expansion_request.md` (if needed)
   * Transition to `BLOCKED`

No background retries.
No parallel agents.

---

# 10. Codex Session Model (Coder + Fixer)

Each `aiw go TASK-###` run permits:

* Exactly one **Coder** session
* At most one **Fixer** session

Fixer session is spawned only if initial test run fails.

## 10.1 Coder Session

* One session per run
* Task-scoped file allowlist enforced
* Produces bounded patch

## 10.2 Fixer Session

* Spawned only after failure
* Produces bounded fix patch
* Must remain within same write scope

Strict limits:

* Maximum iterations per task: 3
* No additional model calls beyond Coder + Fixer
* No cross-task edits

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

# 12. Backend Integration

AIW integrates with Codex CLI in a bounded manner:

* One Codex session per phase invocation
* No streaming orchestration threads
* No autonomous agent loops

Codex output is treated as a patch proposal.
Git diff is authoritative.

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

## ADR-010: Two-Session Codex Model

Each task run permits exactly one Coder session and one Fixer session.

## ADR-011: Deterministic Crash Handling

Stale `EXECUTING` state transitions to `BLOCKED` on startup.

## ADR-012: Hard Constraints Gate

`docs/constraints.yml` and execution gates must validate before `decompose` or `go`.

