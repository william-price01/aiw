## TASK-037: Wire aiw decompose AI session

Type: IMPLEMENTATION
Depends_on: [TASK-036]

Objective:
Replace the `NotImplementedError` stub in `_run_bounded_decompose_ai_session()` with a real
bounded subprocess invocation of the Codex CLI, using the same `codex exec <prompt>` interface
used by the Coder and Fixer sessions.

Context (spec refs):
- PRD §4 (deterministic decomposition outputs), §5.5 (AI mediation — decompose is one bounded
  invocation, not a conversational DRAFT state)
- SDD §5.1 (CONSTRAINTS_APPROVED → PLANNED), §12 (backend integration)
- ADR-009: Execution engine isolation
- constraints.yml: `execution.constraints_finalization_gate`

---

## Background

`aiw decompose` is the gate between the spec phase and the execution phase. It is currently
fully implemented except for one function:

```python
def _run_bounded_decompose_ai_session(
    pcp_paths: PcpPaths,
    prompt: str,
) -> RawDecomposeOutput:
    raise NotImplementedError(
        "bounded decompose AI session is not configured; ..."
    )
```

Everything around it is correct: state validation, constraints gate, prompt construction
(PCP docs concatenated), output validation (DAG.md, DAG.yml, TASK-###.md schema checks),
and atomic write. The only missing piece is the actual AI invocation.

The decompose session differs from the Coder/Fixer sessions in one key way: instead of
writing files to a workspace copy and returning a git diff, it must return a
`RawDecomposeOutput` — a `dict[str, str]` mapping relative `docs/tasks/` paths to file
contents. The AI must be instructed to return structured output in a parseable format.

---

## What (required behavior)

Per SDD §12 and PRD §5.5:
- `aiw decompose` uses exactly one bounded AI invocation.
- The invocation receives the PCP context (prd.md, sdd.md, constraints.yml, adrs/**).
- The invocation is not conversational; it does not persist across turns.
- Output must include DAG.md, DAG.yml, and at least one TASK-###.md.
- Invalid output is rejected before the atomic write (already enforced by
  `validate_decompose_output()`).

---

## Inputs:
- `aiw/orchestrator/decompose.py` (current stub)
- `aiw/orchestrator/decompose_validator.py` (output validation — do not modify)
- `tests/test_decompose_validation.py` (existing validation tests — must continue to pass)
- `tests/test_decompose_orchestration.py` (existing orchestration tests — must continue to pass)

## Outputs (artifacts/files created or changed):
- `aiw/orchestrator/decompose.py` (stub replaced with real invocation)
- `tests/test_decompose_orchestration.py` (extended with failure-mode tests for the AI session)

## File scope allowlist:
- aiw/orchestrator/decompose.py
- tests/test_decompose_orchestration.py

## Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

---

## Implementation contract

### AI invocation interface

Use the same Codex CLI interface as the Coder session:

```python
subprocess.run(
    ("codex", "exec", prompt),
    check=True,
    capture_output=True,
    text=True,
    cwd=<repo_root>,
)
```

The `cwd` should be the repository root (passed through `PcpPaths.root`).

### Output format contract

The prompt must instruct the model to return output as a JSON object mapping relative
`docs/tasks/` paths to full file contents, with no preamble and no markdown fences. Example
required output shape:

```json
{
  "DAG.md": "# DAG...",
  "DAG.yml": "tasks:\n  ...",
  "TASK-001.md": "## TASK-001: ..."
}
```

The system prompt already set in `_DECOMPOSE_SYSTEM_PROMPT` says:
> "Return a mapping of relative docs/tasks paths to full file contents."

The implementation must instruct the model explicitly to return **only valid JSON** with no
surrounding text. Add this to the prompt or as a suffix instruction.

### Parsing

Parse `stdout` of the subprocess as JSON to produce `RawDecomposeOutput`. Strip any surrounding
whitespace. If JSON parsing fails, raise `DecomposeOutputError` with the raw output excerpt in
the message (truncated to 500 chars).

### Error handling

- `subprocess.CalledProcessError` (non-zero exit) → raise `DecomposeOutputError` with stderr
  excerpt.
- `FileNotFoundError` (codex not installed) → raise `DecomposeOutputError` with a clear message:
  `"Codex CLI not found; ensure 'codex' is installed and on PATH"`.
- JSON parse failure → raise `DecomposeOutputError`.

All three failure modes abort the decompose before the atomic write (already guaranteed by the
calling code in `run_decompose()`).

### Test doubles

All tests use a `session_runner` injectable (already present in the calling signature as
`DecomposeSessionRunner`). Do not call the real Codex CLI in tests. The existing
`test_decompose_orchestration.py` already injects stubs; extend it with tests for the three
new failure modes above.

---

## Constraints enforced:
- One bounded AI invocation per `aiw decompose` call (SDD §12).
- No conversational state between decompose invocations.
- Invalid output rejected before atomic write (existing validation layer).

## Non-goals:
- No changes to `decompose_validator.py`.
- No changes to the prompt content beyond adding the JSON-only output instruction.
- No retry logic on AI failure (fail deterministically on first error).
- No streaming output.
- No changes to the Coder or Fixer session implementations.

---

## Acceptance criteria (measurable):

1. `_run_bounded_decompose_ai_session()` no longer raises `NotImplementedError`.
2. When the injected session runner returns valid output, `run_decompose()` succeeds end-to-end.
3. When the Codex CLI exits non-zero, `run_decompose()` raises `DecomposeOutputError` and no
   files are written to `docs/tasks/`.
4. When the Codex CLI is not found, `run_decompose()` raises `DecomposeOutputError` with a
   message containing "Codex CLI not found".
5. When stdout is not valid JSON, `run_decompose()` raises `DecomposeOutputError`.
6. All existing `test_decompose_orchestration.py` and `test_decompose_validation.py` tests pass.
7. New tests in `test_decompose_orchestration.py` cover all three failure modes.

## Tests / checks required:
- `pytest tests/test_decompose_orchestration.py tests/test_decompose_validation.py -q`
- `ruff check .`
- `mypy aiw tests`

## Observability requirements:
- None beyond what the calling code already emits. The AI session itself does not emit trace
  events; the orchestration layer in `run_decompose()` handles that.

## Rollback plan:
- `git checkout` to pre-task baseline.
