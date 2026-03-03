# ADR-011: Deterministic Crash Handling

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

System crashes or abrupt termination during `EXECUTING` can:

* Leave workflow state inconsistent
* Create partial iteration artifacts
* Produce ambiguous restart behavior
* Undermine determinism and reproducibility

Restart semantics must be explicit and deterministic.

---

## Decision

On startup, if `.aiw/workflow_state.json` indicates `EXECUTING`, the system must:

1. Immediately transition state to `BLOCKED`.
2. Record a crash recovery event in:

   ```
   docs/tasks/TASK-###.log.md
   ```
3. Require explicit manual resolution before re-execution.

No automatic resume of partial execution is allowed.

### Crash Detection Includes

* Process interruption (e.g., SIGINT, crash, forced termination)
* Unfinished iteration without checkpoint completion
* Incomplete execution cycle detected at startup

---

## Enforcement Rules

* Crash recovery is mandatory on detection.
* No silent state correction.
* No automatic rollback.
* No continuation from intermediate runtime memory.
* Operator must explicitly invoke retry or reset.

---

## Alternatives Considered

### 1. Automatic Resume of Execution

* Non-deterministic restart surface.
* Hard to validate intermediate correctness.
* Risk of hidden partial state reuse.

### 2. Silent Reset to Prior Checkpoint

* Masks failure condition.
* Reduces operator visibility.
* Breaks explicit workflow semantics.

### 3. Ignore Stale State and Proceed

* Allows undefined behavior.
* Breaks reproducibility guarantees.

---

## Consequences

### Positive

* Deterministic crash recovery behavior.
* Prevents undefined partial state reuse.
* Clear operational semantics.
* Preserves audit trail integrity.

### Negative

* Requires explicit manual unblock step.
* Slight operational friction after crashes.

