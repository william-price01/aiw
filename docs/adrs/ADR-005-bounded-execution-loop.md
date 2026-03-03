# ADR-005: Bounded Execution Loop With Explicit Enforcement

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

Unbounded patch → test → fix loops:

* Increase cost unpredictably
* Risk infinite retry cycles
* Undermine determinism

Additionally, uncontrolled diffs may:

* Violate declared task scope
* Modify unauthorized files
* Circumvent architectural constraints

Strict iteration bounds and pre-apply validation are required.

---

## Decision

Each task execution is limited to **3 iterations maximum**.

### Per Iteration Workflow

1. Validate task scope (preflight).
2. Agent generates changes.
3. Enforce diff validation **before applying changes**:

   * Only allowed files may be modified.
   * Scope boundaries strictly checked.
4. Run tests / lint / typecheck.
5. If success → transition to `COMPLETE`.
6. If failure → next iteration.
7. If 3rd failure → transition to `BLOCKED`.

### Enforcement Properties

* Diff validation occurs **prior to commit or checkpoint**.
* Scope violations count as iteration failures.
* No partial success state is permitted.

---

## Alternatives Considered

### 1. Unlimited Retries

* Unbounded cost.
* Risk of infinite loops.
* Weak failure semantics.

### 2. Configurable Retry Counts

* Expands configuration surface area.
* Encourages tuning instead of proper task decomposition.

### 3. Post-Apply Validation Only

* Allows transient invalid states.
* Increases rollback complexity.
* Weakens enforcement guarantees.

---

## Consequences

### Positive

* Cost-bounded execution.
* Strict scope control.
* Deterministic iteration behavior.
* Clear failure semantics.
* Encourages proper task decomposition upstream.

### Negative

* Complex tasks must be decomposed earlier.
* Some legitimate multi-step fixes may require re-run or change request.
