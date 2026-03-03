# ADR-008: Task Lint Preflight Gate

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

Oversized, ambiguous, or under-specified tasks:

* Degrade bounded execution guarantees
* Increase iteration failure probability
* Violate 1–3 iteration completion constraint
* Introduce nondeterministic scope expansion

Tasks must remain independently verifiable, deterministic, and small.

A formal preflight gate is required before execution.

---

## Decision

Before execution, each task must pass a **preflight lint gate**.

If lint fails, execution is rejected.

### Validation Rules (Mandatory)

* Explicit objective defined
* Acceptance criteria measurable
* File scope specified (allow paths or files)
* ≤ 2 modules modified (hard limit for MVP)
* Dependencies declared
* Non-goals listed

### Enforcement Behavior

* Lint runs before `PLANNED → EXECUTING`.
* Failure results in hard rejection of execution.
* No partial execution is allowed.
* User must revise or regenerate task before retry.

---

## Alternatives Considered

### 1. Allow Free-Form Tasks

* Encourages scope drift.
* Breaks bounded iteration model.

### 2. Manual Review Only

* Non-deterministic enforcement.
* Inconsistent application.

### 3. Soft Recommendation Without Enforcement

* No structural guarantees.
* Fails to protect execution bounds.

---

## Consequences

### Positive

* Enforces small, testable work units.
* Protects bounded execution loop.
* Improves task clarity.
* Strengthens reproducibility guarantees.

### Negative

* Requires upfront task discipline.
* May require task splitting before execution.
