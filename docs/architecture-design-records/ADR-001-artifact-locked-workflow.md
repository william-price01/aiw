# ADR-001: Artifact-Locked Workflow

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

The `aiw` system relies on deterministic artifacts as the authoritative source of truth:

* `PRD.md`
* `SDD.md`
* `tasks/`
* `constraints.yml`

Uncontrolled edits during active execution introduce:

* Nondeterminism
* Scope drift
* Mid-task requirement mutation
* Loss of reproducibility

The workflow must strictly prevent mutation of approved artifacts while tasks are executing.

---

## Decision

Approved artifacts are immutable while the workflow is in an execution state.

### Lock Rules

* Once an artifact reaches `APPROVED`, it becomes read-only.
* No direct edits are permitted.
* Modifications require a formal **Change Request (CR)**.
* CR must explicitly reference impacted artifact(s).
* Workflow must transition to a non-execution state before applying a CR.
* Lock enforcement occurs via state validation in:

```
.aiw/workflow_state.json
```

* No implicit mutation of approved documents is permitted.

---

## Alternatives Considered

### 1. Soft Lock with Warnings Only

* Does not prevent nondeterministic changes.
* Easy to bypass.

### 2. Git-Based Diff Monitoring Without Enforcement

* Reactive rather than preventive.
* Does not guarantee execution integrity.

### 3. Allow Edits with Automatic Re-Approval

* Introduces silent state mutation.
* Weakens artifact authority.

---

## Consequences

### Positive

* Enforces architectural discipline.
* Preserves reproducibility.
* Prevents hidden scope mutation during execution.
* Maintains deterministic task execution.

### Negative

* Adds friction for rapid iteration.
* Requires explicit Change Request flow implementation.
* Increases formal process overhead.
