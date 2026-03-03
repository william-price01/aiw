# ADR-012: Hard Constraints Gate

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

`docs/constraints.yml` encodes architectural boundaries, including:

* Allowed dependency directions
* Do-not-touch paths
* File path boundaries
* Quality gates (tests, lint, typecheck)

If these constraints are not validated prior to decomposition or execution:

* Architectural drift becomes likely
* Illegal module coupling may occur
* Scope violations may propagate silently
* Enforcement becomes reactive instead of preventive

Constraints must be enforced as a hard gate.

---

## Decision

`constraints.yml` validation is mandatory before:

* `aiw decompose`
* `aiw go`

If validation fails, the command aborts immediately.

### Validation Requirements

The system must verify:

* File path boundaries are defined and coherent.
* Allowed dependency directions are declared.
* Required test / lint / typecheck commands are defined.
* Mandatory quality rules are present.
* Do-not-touch paths are declared where applicable.

Validation is:

* Deterministic
* Blocking
* Enforced prior to execution or decomposition

No advisory-only mode is permitted.

---

## Alternatives Considered

### 1. Advisory Constraints Only

* Non-enforced guidance.
* Easily bypassed.
* Encourages architectural drift.

### 2. Post-Execution Constraint Validation

* Reactive instead of preventive.
* Allows illegal states to occur transiently.

### 3. Manual Architectural Review

* Non-deterministic enforcement.
* Not scalable.
* Dependent on human vigilance.

---

## Consequences

### Positive

* Enforces architectural contracts.
* Prevents illegal module coupling.
* Preserves system integrity.
* Maintains deterministic enforcement surface.

### Negative

* Adds validation overhead before execution.
* Requires disciplined maintenance of `constraints.yml`.
