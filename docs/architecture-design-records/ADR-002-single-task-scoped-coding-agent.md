# ADR-002: Single Task-Scoped Coding Agent

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

Unbounded agent context introduces:

* Cross-task memory leakage
* Nondeterministic behavior
* Hidden dependency coupling

The design goal of `aiw` is strict task isolation with reproducible patch cycles.
Each task must be independently verifiable within **1–3 iterations**.

Shared or persistent agents undermine determinism and auditability.

---

## Decision

Each `aiw go TASK-###` invocation:

* Spawns **exactly one** Codex session.
* The agent is scoped to that task only.
* The agent receives:

  * Task definition
  * Relevant artifacts
  * `constraints.yml`
  * Relevant code context
* No cross-task conversational memory is permitted.
* Agent terminates upon:

  * Task completion (success), or
  * Iteration exhaustion (failure)

New task → new agent instance.

There is **never more than one active coding agent per task execution**.

---

## Alternatives Considered

### 1. Long-Lived Shared Agent Across Tasks

* Increases context bloat.
* Introduces hidden state carryover.
* Reduces reproducibility.

### 2. Parallel Multi-Agent Execution

* Increases orchestration complexity.
* Introduces race conditions.
* Complicates audit and rollback.

### 3. Agent Pool Reuse

* Reduces session overhead.
* Reintroduces state leakage risk.

---

## Consequences

### Positive

* Strong isolation guarantees.
* Deterministic task boundaries.
* Reduced context bloat.
* Easier rollback and audit.
* Clear execution semantics.

### Negative

* Slight overhead in session creation.
* No automatic knowledge carryover between tasks.
