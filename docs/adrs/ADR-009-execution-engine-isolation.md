# ADR-009: Execution Engine Isolation

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

`aiw` separates:

* Task selection (backlog management, prioritization)
* Task execution (`aiw go`)

Coupling these concerns introduces:

* Hidden dependencies
* Implicit task mutation
* Nondeterministic execution paths
* Blurred responsibility boundaries

The execution engine must operate strictly on a resolved, explicit task definition.

---

## Decision

The task execution engine is isolated from task selection logic.

### Invocation Rule

`aiw go TASK-###` requires an explicit task ID.

No implicit task resolution is permitted.

### Execution Inputs (Exclusive)

Execution reads only:

* Task definition file (`docs/tasks/TASK-###.md`)
* Approved artifacts (`docs/prd.md`, `docs/sdd.md`, `docs/adrs/`)
* `docs/constraints.yml`
* `.aiw/workflow_state.json`
* Workspace state (via Git)

### Explicit Prohibitions

The execution engine must not:

* Perform dynamic task discovery
* Perform prioritization
* Mutate backlog state
* Resolve “next task” automatically
* Modify task definitions

Selection logic (e.g., next-task resolution) is implemented as a separate command and module.

### Determinism Requirement

The execution engine is a pure function of:

* Task input
* Approved artifacts
* Workspace state

No external selection logic influences execution behavior.

---

## Alternatives Considered

### 1. Automatic “Next Task” Execution

* Introduces implicit sequencing.
* Reduces execution determinism.

### 2. Execution Engine Auto-Selecting Tasks via Dependency Graph

* Blurs separation of concerns.
* Complicates testing.
* Couples runtime to planning layer.

### 3. Integrated Backlog + Execution Runtime

* Increases architectural complexity.
* Harder to isolate execution bugs.
* Weakens contract boundaries.

---

## Consequences

### Positive

* Clear separation of concerns.
* Deterministic execution surface.
* Easier testing and debugging of execution engine.
* Simplified mental model.

### Negative

* Requires explicit task invocation.
* Slightly more manual workflow control.

