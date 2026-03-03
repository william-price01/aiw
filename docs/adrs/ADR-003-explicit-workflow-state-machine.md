# ADR-003: Explicit Workflow State Machine

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

Implicit workflow inference (e.g., deriving state from file existence) is ambiguous and error-prone.

Without strict gating:

* Illegal command sequences can execute.
* Execution may occur before required approvals.
* Artifact locks may be bypassed.
* Reproducibility guarantees degrade.

Deterministic state control is required.

---

## Decision

Workflow state is stored explicitly in:

```text
.aiw/workflow_state.json
```

Execution commands must validate allowed transitions before proceeding.

### Minimum States

```text
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

* Every command checks current state before execution.
* Transitions are validated against a deterministic transition table.
* Invalid transitions cause immediate termination.
* No implicit state inference from filesystem structure.
* No fallback logic based on file presence.

---

## Alternatives Considered

### 1. Stateless CLI

* No enforcement mechanism.
* Allows invalid sequencing.
* Breaks deterministic workflow guarantees.

### 2. Git-Branch–Derived State

* Couples workflow to version control semantics.
* Harder to validate programmatically.
* Adds unnecessary complexity.

### 3. File-Existence Inference

* Ambiguous.
* Vulnerable to manual edits.
* Not reliably enforceable.

---

## Consequences

### Positive

* Deterministic enforcement of workflow rules.
* Clear operational boundaries.
* Explicit lifecycle visibility.
* Improved auditability.

### Negative

* Requires maintaining a transition table.
* Adds minimal state serialization overhead.
