# ADR-004: Markdown Capsule Memory

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

Hidden memory mechanisms (e.g., JSON blobs, agent-side persistence, opaque state files) reduce auditability and weaken reproducibility guarantees.

Task reasoning and iteration history must remain:

* Transparent
* Human-readable
* Version-controlled
* Deterministic

Persistent memory must not introduce hidden state or implicit coupling across runs.

---

## Decision

Task memory is stored in:

```text id="capsule-path"
docs/tasks/TASK-###.log.md
```

### Rules

* Append-only during execution
* Human-readable Markdown
* No hidden structured memory (JSON, DB, binary state)
* No external memory stores
* No conversational persistence

### Required Contents

The file must contain:

* Attempt summaries
* Failures encountered
* Patch rationale
* Test results
* Status transitions

This file is the **sole persistent memory** for the task.

No additional memory artifacts are permitted.

---

## Alternatives Considered

### 1. Hidden JSON State

* Opaque to humans
* Harder to audit
* Encourages hidden coupling

### 2. Database-Backed Memory

* Adds infrastructure complexity
* Violates local-first design constraints

### 3. Persistent Conversational Context

* Introduces nondeterminism
* Breaks strict task isolation

---

## Consequences

### Positive

* Fully auditable
* Git-friendly diffs
* Clear iteration trace
* Deterministic persistence boundary

### Negative

* Slight verbosity overhead
* Requires disciplined logging conventions

