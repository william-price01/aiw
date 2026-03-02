# ADR-003: Explicit Workflow State Machine

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

Implicit workflow transitions introduce:

* Ambiguity in execution rules
* Inconsistent enforcement of command sequencing
* Risk of illegal operations (e.g., running coding before SDD approval)

The system requires deterministic state gating to guarantee:

* Correct command ordering
* Artifact lock enforcement
* Reproducible workflow progression

State must be explicit and authoritative.

---

## Decision

Workflow state is explicitly stored in:

```id="wfstate"
.aiw/workflow_state.json
```

The state machine is strictly enforced.

### Valid States (Minimum)

```id="states"
INIT
PRD_DRAFT
PRD_APPROVED
SDD_DRAFT
SDD_APPROVED
TASKS_READY
EXECUTING
BLOCKED
COMPLETE
```

### Enforcement Rules

* All commands validate current state before execution.
* Transitions are deterministic.
* Invalid transitions cause immediate failure.
* No implicit state inference from filesystem contents.
* Filesystem presence does not determine workflow stage.

---

## Alternatives Considered

### 1. Deriving State from File Presence

* Ambiguous.
* Susceptible to manual edits.
* Not reliably enforceable.

### 2. Stateless Command Execution

* No gating mechanism.
* Allows invalid sequencing.
* Breaks determinism.

### 3. Git Branch–Based Workflow State

* Couples workflow to VCS semantics.
* Adds unnecessary complexity.
* Harder to validate programmatically.

---

## Consequences

### Positive

* Deterministic command enforcement.
* Prevents illegal command sequences.
* Enables terminal visualization of workflow progression.
* Clear, auditable lifecycle transitions.

### Negative

* Requires explicit state transition logic maintenance.
* Adds minimal state serialization overhead.
