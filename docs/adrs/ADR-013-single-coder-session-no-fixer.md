# ADR-013: Single Coder Session — No Fixer, No Iteration Cap

**Date:** 2026-03-10
**Status:** Accepted
**Supersedes:** ADR-010 (Two-Session Codex Model)

---

## Context

ADR-010 defined a Coder + Fixer model: one Coder session generates the initial patch; if tests
fail, one Fixer session is spawned to attempt a repair; if the Fixer also fails, the task
transitions to BLOCKED.

This model has the following problems:

* A Fixer session receives no additional context beyond "the first attempt failed." It cannot
  diagnose root cause reliably and is likely to produce noise rather than signal.
* The iteration cap (`max_iterations_per_task: 3`) was meaningful only in the context of
  multiple retry passes. Without meaningful retries, it is an arbitrary number that implies
  resilience the system does not have.
* Real quality signal comes from the test harness, not from a second AI pass on a failed diff.
* Future integrations (static analysis gates, external diff review tools) fit cleanly between
  patch application and test execution — they do not require an agent retry loop.
* The Fixer adds complexity (a second session lifecycle, additional trace events, additional
  executor branching) with no corresponding reliability benefit.

---

## Decision

Each `aiw go TASK-###` run permits **exactly one Coder session**. There is no Fixer session.
There is no iteration cap.

### Execution Model

1. Coder session generates patch.
2. Patch is validated (scope, diff thresholds, locked artifact checks).
3. Tests run.
4. If PASS → `PLANNED`.
5. If FAIL → `BLOCKED`. No retry. No second session.

### Termination Semantics

| Outcome | Transition |
|---|---|
| Tests pass | `EXECUTING → PLANNED` |
| Tests fail | `EXECUTING → BLOCKED` |
| Patch validation fails | `EXECUTING → BLOCKED` |
| Coder session error | `EXECUTING → BLOCKED` |

All paths are deterministic and terminate in one pass.

### Failure Reason Vocabulary

The `blocked` trace event payload uses `failure_reason` with the following values:

- `test_failed` — tests ran and failed
- `patch_validation_failed` — scope or diff threshold violation
- `coder_session_error` — Codex invocation failed

`iteration_exhausted` and `fixer_spawned` are removed from the trace event vocabulary.

### Removed

* `fixer.py` module
* `FixerRunner` type
* `fixer_runner` parameter on `execute_task()`
* `iterations_used` field on `ExecutionResult`
* `max_iterations_per_task` field in `ConstraintsConfig` and `constraints.yml`
* `fixer_spawned` and `iteration_exhausted` trace event types

---

## Alternatives Considered

### 1. Keep Fixer, Remove Iteration Cap

* Fixer still adds complexity with no reliable quality benefit.
* Rejected.

### 2. Multiple Independent Coder Retries (No Fixer)

* Retrying with the same prompt and same context is unlikely to produce a different result.
* Legitimate retry scenarios (transient environment issues) are better handled by the operator
  re-running `aiw go` after diagnosing the failure.
* Rejected.

### 3. Keep Fixer, Wire to External Reviewer

* External review tools (e.g. CodeRabbit) are better positioned as a gate on the Coder output,
  not as a trigger for a second AI pass.
* External integrations belong between patch application and test execution, not as a retry
  mechanism.
* Deferred as a future extension; does not require Fixer to exist.

---

## Consequences

### Positive

* Simpler executor: one session, two terminal states, no branching on retry count.
* Smaller test surface: `test_fixer.py` and `test_executor_fixer.py` removed.
* Cleaner trace event vocabulary: 12 required events instead of 14.
* `constraints.yml` no longer carries a meaningless iteration count.
* Future quality gate integrations (slopgate, external diff review) fit naturally as a
  pre-test validation step with no executor changes required.

### Negative

* No automatic recovery from a failing patch within a single `aiw go` invocation.
* Operator must diagnose and re-run manually after BLOCKED. This is intentional — the test
  harness and task decomposition quality are the correctness mechanisms, not agent retries.
