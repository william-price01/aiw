# ADR-004: Markdown Capsule Memory

**Date:** 2026-02-25
**Status:** Accepted

---

## Context

AI systems commonly store hidden JSON logs or opaque state files that obscure task history.

For reproducibility and auditability, task memory must be:

* Transparent
* Human-readable
* Version-controlled

Each task may require limited persistent notes across bounded iterations.
This memory must not introduce hidden state or nondeterministic behavior.

---

## Decision

Task memory is stored as:

```id="capsule"
tasks/TASK-###.log.md
```

### Rules

* Markdown only
* Append-only during execution
* No hidden JSON memory blobs
* No external memory stores
* No database-backed persistence

### Contents

The file may contain:

* Attempt summaries
* Failures encountered
* Patch rationale
* Test outcomes
* Iteration counters
* Diff summaries (if relevant)

This file is the **sole persistent memory** for that task.

No other memory artifacts are permitted.

---

## Alternatives Considered

### 1. Hidden JSON State Files

* Opaque to humans
* Harder to audit
* Encourages hidden coupling

### 2. Database-Backed Memory

* Adds infrastructure complexity
* Violates local-first minimalism

### 3. Long-Lived Conversational Context

* Introduces nondeterminism
* Breaks strict task isolation

---

## Consequences

### Positive

* Fully auditable
* Git-diff friendly
* Human-readable debugging trace
* Deterministic persistence boundary

### Negative

* Slight verbosity
* Requires disciplined, structured logging conventions
