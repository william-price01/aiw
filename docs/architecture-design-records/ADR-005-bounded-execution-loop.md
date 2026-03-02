# ADR-005: Bounded Execution Loop

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

Unbounded patch → test → fix loops:

* Increase cost unpredictably
* Risk infinite retry cycles
* Undermine determinism

The system must remain:

* Cost-aware
* Deterministic
* Strictly scoped

Tasks are constrained to be completable within **1–3 iterations**.

---

## Decision

Execution loop per task is bounded to a maximum of **3 iterations**.

### Loop Structure

1. Agent generates patch.
2. Tests / lint / typecheck are executed.
3. If success → transition to `COMPLETE`.
4. If failure → proceed to next iteration.
5. If `iteration == 3` and still failing → transition to `BLOCKED`.

### Upon `BLOCKED`

* Execution halts immediately.
* Summary written to:

```id="blocked-log"
tasks/TASK-###.log.md
```

* Manual intervention required.
* No automatic retries beyond 3 attempts.

---

## Alternatives Considered

### 1. Unlimited Retries

* Unbounded cost.
* Risk of infinite loops.
* Weak failure semantics.

### 2. Configurable Retry Count

* Adds configuration surface area.
* Encourages tuning instead of proper task scoping.

### 3. Automatic Fallback Model Switching

* Increases system complexity.
* Reduces determinism.
* Introduces hidden branching behavior.

---

## Consequences

### Positive

* Prevents runaway cost.
* Enforces tight task scoping.
* Clear and deterministic failure semantics.
* Encourages decomposition of oversized tasks.

### Negative

* Some tasks may require splitting.
* Requires manual unblock step for complex failures.
