# ADR-006: Git-Based Checkpointing Per Iteration

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

Reproducibility requires deterministic rollback points.

Without structured checkpoints:

* Manual resets are error-prone
* Iteration boundaries become ambiguous
* Partial rollbacks risk corrupt state
* Audit trails become unclear

Rollback must be:

* Deterministic
* Minimal
* Native to the repository
* Independent of hidden state

---

## Decision

Each iteration creates a **Git checkpoint commit**.

### Rules

* Exactly one checkpoint per iteration.
* Commit message must include:

  * `TASK-###`
  * Iteration number
* Checkpoint creation occurs **before the next iteration begins**.
* `undo` and `reset` operations rely solely on Git history.
* No secondary snapshot mechanism is allowed.
* No file-copy backups.
* No hidden state mirrors.

### Enforcement

Checkpoint boundaries define iteration boundaries.
All rollback operations resolve to these commits.

---

## Alternatives Considered

### 1. Single Commit at Task End

* No granular rollback.
* Breaks iteration isolation.
* Harder to debug mid-loop failures.

### 2. Non-Git Snapshots

* Introduces parallel state system.
* Violates minimalism.
* Increases complexity.

### 3. File Copy Backups

* Fragile.
* Non-atomic.
* Hard to audit.
* Not version-controlled.

---

## Consequences

### Positive

* Deterministic undo/reset semantics.
* Native Git integration.
* Clear historical trace per iteration.
* Transparent audit trail.

### Negative

* Increased commit volume.
* Slight repository history noise.
