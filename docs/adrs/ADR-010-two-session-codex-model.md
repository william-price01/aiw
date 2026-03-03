# ADR-010: Two-Session Codex Model

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

Single-session models blur responsibilities between initial implementation and corrective reasoning.

Unbounded retry loops:

* Increase cost
* Reduce determinism
* Encourage iterative drift
* Complicate auditability

A bounded, role-separated model improves clarity and predictability.

---

## Decision

Each task run permits exactly:

* **One Coder session**
* **One Fixer session**

### Execution Structure

1. **Coder session**

   * Generates initial implementation.
2. Tests / lint / typecheck execute.
3. If success → transition to `COMPLETE`.
4. If failure:

   * Exactly one **Fixer session** is allowed.
5. Tests re-run.
6. If still failing → transition to `BLOCKED`.

No additional model sessions are permitted.

This constraint exists within the broader bounded execution loop
(max 3 iterations including validation passes).

---

## Enforcement Rules

* A task run may not spawn more than two model sessions.
* No fallback sessions.
* No parallel fix attempts.
* No hidden retry loops.

Session count is validated in execution runtime.

---

## Alternatives Considered

### 1. Unlimited Retry Sessions

* Unbounded cost.
* Reduced determinism.
* Risk of runaway loops.

### 2. Single Blended Coder/Fixer Loop

* Blurs responsibility boundaries.
* Harder to reason about failure modes.

### 3. Multiple Parallel Fix Attempts

* Increased orchestration complexity.
* Nondeterministic outcome selection.

---

## Consequences

### Positive

* Strong cost control.
* Clear separation of responsibilities.
* Deterministic execution semantics.
* Predictable failure boundary.

### Negative

* Complex fixes may require task decomposition.
* Less adaptive than multi-retry systems.
