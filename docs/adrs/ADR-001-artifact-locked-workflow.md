# ADR-001: Artifact-Locked Workflow

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

`aiw` relies on deterministic artifacts as authoritative contracts:

* `docs/prd.md`
* `docs/sdd.md`
* `docs/constraints.yml`
* `docs/tasks/` definitions

Modifying approved documents during execution:

* Introduces nondeterminism
* Breaks reproducibility guarantees
* Invalidates iteration integrity
* Enables mid-task scope mutation

Strict immutability during execution is required to preserve deterministic behavior.

---

## Decision

Approved artifacts are immutable once the workflow enters `EXECUTING`.

### Enforcement Rules

* Any modification attempt during `EXECUTING` results in **immediate hard failure**.
* Changes require:

  1. Exiting execution state
  2. Initiating a formal change request
* Enforcement is validated against:

```text
.aiw/workflow_state.json
```

### Lock Scope

The lock applies to:

* `docs/prd.md`
* `docs/sdd.md`
* `docs/constraints.yml`
* All `docs/tasks/` definitions

No soft warnings.
No advisory logs.
Enforcement is strict and blocking.

---

## Alternatives Considered

### 1. Warning-Only Enforcement

* Does not prevent nondeterministic mutation.
* Easily bypassed.

### 2. Git-Diff Detection Without Failure

* Reactive rather than preventative.
* Allows invalid state progression.

### 3. Automatic Re-Approval Workflow

* Introduces implicit transitions.
* Weakens artifact authority.
* Encourages uncontrolled mutation cycles.

---

## Consequences

### Positive

* Preserves deterministic builds.
* Prevents scope drift mid-task.
* Enables reproducible iteration cycles.
* Maintains strong contract semantics between phases.

### Negative

* Adds friction when rapid changes are desired.
* Requires explicit change request handling for legitimate updates.

