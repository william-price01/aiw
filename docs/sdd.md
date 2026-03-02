# SDD: aiw (AI Workflow) — Local AI Coding Orchestrator

This revision corrects:

* `aiw init` scaffolding (authoritative structure)
* Explicit, enforceable workflow state machine
* Strict single-task-scoped coding agent model
* Locked artifact + change request rules
* Bounded execution loop as a formal state machine

The system remains minimal, local-first, single-process, and speed-optimized.

---

# 1. System Overview

`aiw` is a local CLI AI coding orchestrator for a single advanced developer.

It provides:

* Deterministic artifacts (PRD, SDD, tasks)
* Strict workflow state locking
* Task-scoped coding agents
* Bounded patch → test → fix loop
* JSONL structured tracing
* Terminal tree-style observability
* Git-based undo/reset

No SaaS.
No daemon.
No distributed components.
No cross-task conversational memory.

All persistence is artifact-based.

---

# 2. Authoritative `aiw init` Scaffold

## 2.1 User-Facing Artifacts (Editable by User)

Created in repository root:

```
PRD.md
SDD.md
constraints.yml
adrs/
tasks/
```

### Purpose

| Artifact          | Owner         | Description                   |
| ----------------- | ------------- | ----------------------------- |
| `PRD.md`          | User-authored | Product requirements          |
| `SDD.md`          | User-authored | System design                 |
| `constraints.yml` | User-authored | Architecture boundaries       |
| `adrs/`           | User-authored | Architecture Decision Records |
| `tasks/`          | User-authored | TASK-###.md files             |

These are **version-controlled artifacts** and define system truth.

---

## 2.2 Tool-Internal State (Not User-Authored)

Created under:

```
.aiw/
  agents/
  workflow_state.json
  runs/
```

### Purpose

| Path                       | Description                                  |
| -------------------------- | -------------------------------------------- |
| `.aiw/agents/`             | Prompt templates for PRD/SDD/Decompose/Coder |
| `.aiw/workflow_state.json` | Workflow state + lock tracking               |
| `.aiw/runs/`               | Per-run JSONL event traces                   |

No additional scaffolding is created.
No memory directory.
No hidden task state.
All task persistence is artifact-based.

---

# 3. Global Workflow State Machine

The system is governed by a strict workflow state machine stored in:

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
PLANNED
EXECUTING
BLOCKED
```

---

## State Definitions

### INIT

**Allowed Commands**

* `aiw prd`
* `aiw init`

**Transition**

* Writing PRD → `PRD_DRAFT`

---

### PRD_DRAFT

**Allowed**

* Edit `PRD.md`
* `aiw approve-prd`

**Transition**

* Approve → `PRD_APPROVED`

---

### PRD_APPROVED (LOCKED)

PRD becomes immutable.

**Allowed**

* `aiw sdd`
* `aiw request-change`

PRD cannot be edited directly.

---

### SDD_DRAFT

**Allowed**

* Edit `SDD.md`
* `aiw approve-sdd`

**Transition**

* Approve → `SDD_APPROVED`

---

### SDD_APPROVED (LOCKED)

SDD becomes immutable.

**Allowed**

* `aiw decompose`
* `aiw request-change`

---

### PLANNED

Tasks generated.

**Allowed**

* `aiw go TASK-###`

---

### EXECUTING

One TASK in execution.

**Allowed**

* No PRD/SDD modification
* Only task execution
* `aiw undo`
* `aiw reset`

**Transitions**

* On success → `PLANNED`
* On exhaustion → `BLOCKED`

---

### BLOCKED

Execution failed after max iterations.

**Allowed**

* `aiw request-change`
* `aiw go TASK-###` (retry)

---

# 4. Locking Rules (Mandatory)

Once approved:

* `PRD.md` cannot be modified.
* `SDD.md` cannot be modified.

Edits require a Change Request.

Direct file modification triggers hard failure.

---

# 5. Minimal Change Request Mechanism

When downstream execution requires upstream modification:

1. Create:

```
CHANGE_REQUEST.md
```

2. Must contain:

* Reason
* Affected section
* Proposed change

3. Approval required:

* Reverts state to `PRD_DRAFT` or `SDD_DRAFT`
* Requires re-approval

Silent upstream edits are prohibited.

---

# 6. Coding Loop State Machine (EXECUTING)

Within `EXECUTING`:

```
CONTEXT_PACK
→ PATCH_WRITE
→ APPLY_PATCH
→ RUN_TESTS
→ PASS | FAIL
```

If `FAIL`:

```
ERROR_EXTRACT
→ FIX_ATTEMPT (iteration++)
→ repeat
```

Hard cap:

```
max_iterations = 3 (default)
```

If exceeded:

* Generate `tasks/TASK-###/blocker_report.md`
* Transition to `BLOCKED`

---

# 7. Task-Scoped Coding Agent Model (Hard Requirement)

Each `aiw go TASK-###`:

```
SPAWN_AGENT(TASK-###)
→ bounded loop
→ TERMINATE_AGENT
```

### Rules

A coding agent:

* Works on exactly one task
* Has no memory beyond current run
* Does not access other TASK files
* Is destroyed after execution completes

Each run = new Codex session.

---

# 8. Task Context Boundary

Agent receives only:

* `tasks/TASK-###.md`
* `constraints.yml`
* Relevant code snippets
* Relevant diffs
* Relevant test excerpts
* `tasks/TASK-###.log.md` (capsule)

No cross-task memory.
No global conversational memory.

Knowledge flows only through committed artifacts.

---

# 9. Capsule Memory Model

Per task:

```
tasks/TASK-###.log.md
```

Contains:

* Iteration summaries
* Diffstats
* Failure excerpts
* Status

No JSON capsule.
Human-readable Markdown only.

Bounded size enforced.

---

# 10. TUI Rendering Model

TUI shows:

```
TASK-001
└── CodexAgent
    ├── RepoScan
    ├── PatchWrite
    ├── ApplyPatch
    ├── TestRun
    └── FixAttempt (if any)
```

There is exactly one Codex agent instance per task execution.

Subagents are logical spans only.

---

# 11. Execution Flow Updates

## `aiw go TASK-###`

1. Validate workflow state = `PLANNED`
2. Transition → `EXECUTING`
3. Spawn Codex agent
4. Run bounded loop
5. On success:

   * Terminate agent
   * Transition → `PLANNED`
6. On exhaustion:

   * Write blocker report
   * Transition → `BLOCKED`

---

# 12. Backend Integration (Codex CLI)

Backend lifecycle:

```
SPAWN
→ propose_patch(context)
→ return unified diff
→ TERMINATE
```

Must output unified diff only.

No session reuse.
No multi-task reuse.

---

# 13. Failure Handling

### Patch Violates Scope

* Abort iteration
* Count as failure

### Tests Fail

* Extract bounded excerpt
* Append to `TASK-###.log.md`

### Iteration Cap Exceeded

* Write blocker report
* Transition to `BLOCKED`

---

# 14. Undo / Reset

### `aiw undo`

* Git reset to previous snapshot

### `aiw reset TASK-###`

* Git reset to pre-task snapshot
* Clear `TASK-###.log.md`

Snapshots recorded per iteration.

---

# 15. File Structure (Corrected)

```
PRD.md
SDD.md
constraints.yml
CHANGE_REQUEST.md (if exists)
adrs/
tasks/
  TASK-001.md
  TASK-001.log.md
  TASK-001/
    blocker_report.md
.aiw/
  agents/
  workflow_state.json
  runs/
    run-<timestamp>.jsonl
```

No additional directories.

---

# 16. Consistency Guarantees

* One coding agent per task run
* Locked upstream docs after approval
* Deterministic bounded loop
* Artifact-based persistence only
* No cross-task conversational memory

---

# 17. Architecture Decision Records (Updated)

## ADR-001: Artifact-Locked Workflow

Approved docs become immutable until change request resolves.

## ADR-002: Single Task-Scoped Coding Agent

Each `aiw go` spawns exactly one Codex session.

## ADR-003: Explicit Workflow State Machine

State stored in `.aiw/workflow_state.json` and strictly enforced.

## ADR-004: Markdown Capsule Memory

Task memory stored in `TASK-###.log.md` (not hidden JSON).

## ADR-005: Bounded Execution Loop

Max 3 iterations. Hard transition to `BLOCKED` on exhaustion.

