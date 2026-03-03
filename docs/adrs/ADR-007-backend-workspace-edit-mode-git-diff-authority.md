# ADR-007: Backend Workspace-Edit Mode With Git Diff as Source of Truth

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

Model-generated file rewrites can diverge from actual workspace state if changes are tracked through abstract patch objects or secondary representations.

To preserve determinism and developer-aligned workflows:

* The authoritative record of change must reflect the real repository state.
* Enforcement must operate on concrete filesystem modifications.
* Change tracking must remain transparent and auditable.

Git is the canonical source of repository truth.

---

## Decision

The backend operates in **workspace-edit mode**.

### Operational Model

* The agent writes changes directly to the working tree.
* `git diff` is the authoritative representation of modifications.
* Validation and enforcement operate exclusively on Git diff output.
* Optional diff-only output mode may be supported.
* No separate patch abstraction exists outside Git.
* No virtual filesystem layer is introduced.
* No JSON-based change representation is authoritative.

### Enforcement Boundary

All scope validation, diff size limits, and lock checks inspect:

```text
git diff
git diff --name-only
```

Git is the single source of truth for file mutations.

---

## Alternatives Considered

### 1. Patch File Abstraction

* Adds redundant representation layer.
* Risks divergence from workspace state.
* Increases complexity.

### 2. Virtual Filesystem Layer

* Introduces architectural overhead.
* Complicates debugging.
* Weakens alignment with developer workflows.

### 3. JSON-Based Change Representation

* Non-native to repository.
* Requires translation layer.
* Harder to audit.

---

## Consequences

### Positive

* Aligns with standard developer workflows.
* Simplifies validation and enforcement logic.
* Transparent change tracking.
* Deterministic state inspection.

### Negative

* Requires Git availability.
* Increases reliance on clean repository state management.
