## TASK-038: CLI user feedback — print confirmation output for all commands

Type: IMPLEMENTATION
Depends_on: [TASK-037]

Objective:
Add stdout confirmation output to every `aiw` CLI command so the operator knows what happened.
Currently all dispatch handlers call their backing functions and return silently with no output.
A live run gives zero feedback.

Context (spec refs):
- PRD §2 (target user: advanced developer, values speed — output must be concise and direct)
- PRD §5.2 (command allowance by state — operators need to know the resulting state)
- SDD §15 (TUI rendering model — derives from state, artifacts, and traces)

---

## Background

Every `_dispatch_*` handler in `aiw/cli/main.py` calls its backing function and discards the
return value without printing anything. For example:

```python
def _dispatch_prd(_: argparse.Namespace, root: Path) -> None:
    prd(root)                    # SpecDraftSession returned and silently discarded
```

Running `aiw prd`, `aiw approve-prd`, `aiw go TASK-###`, etc. produces no stdout output.
The operator has no confirmation that the command succeeded, what the resulting state is, or
where artifacts were written. This is a usability blocker for a live run.

---

## What (required behavior)

This is a HOW-level addition. No behavioral changes to any underlying function.
Only the dispatch handlers change: they must print a confirmation line to stdout.

The output must be minimal and machine-friendly. One line per command is sufficient.
Format: `ok: <what happened> [state: <new_state>]`

---

## Inputs:
- `aiw/cli/main.py` (all `_dispatch_*` handlers)
- `tests/test_cli_router.py` (existing router tests — must pass)
- `tests/test_cli_state.py` (existing state tests — must pass)

## Outputs (artifacts/files created or changed):
- `aiw/cli/main.py` (dispatch handlers updated)
- `tests/test_cli_router.py` (extended to assert stdout contains expected confirmation)

## File scope allowlist:
- aiw/cli/main.py
- tests/test_cli_router.py

## Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

---

## Required output per command

| Command | Stdout line |
|---|---|
| `aiw init` | `ok: initialized .aiw/ [state: INIT]` |
| `aiw prd` | `ok: entered PRD drafting [state: PRD_DRAFT]` |
| `aiw approve-prd` | `ok: PRD approved and locked [state: PRD_APPROVED]` |
| `aiw sdd` | `ok: entered SDD drafting [state: SDD_DRAFT]` |
| `aiw approve-sdd` | `ok: SDD approved and locked [state: SDD_APPROVED]` |
| `aiw adrs` | `ok: entered ADR drafting [state: ADRS_DRAFT]` |
| `aiw approve-adrs` | `ok: ADRs approved and locked [state: ADRS_APPROVED]` |
| `aiw constraints` | `ok: entered constraints drafting [state: CONSTRAINTS_DRAFT]` |
| `aiw approve-constraints` | `ok: constraints approved and locked [state: CONSTRAINTS_APPROVED]` |
| `aiw decompose` | `ok: decomposed into N tasks [state: PLANNED]` (N = number of TASK files written) |
| `aiw go TASK-###` | `ok: TASK-### PASS [run_id: <uuid>]` or `blocked: TASK-### BLOCKED [run_id: <uuid>]` |
| `aiw undo` | `ok: reverted to last checkpoint` |
| `aiw reset TASK-###` | `ok: reset to TASK-### baseline` |
| `aiw request-change` | `ok: change request written to docs/requests/CHANGE_REQUEST.md` |

For `aiw go`:
- Print to stdout on PASS.
- Print to stderr (and return exit code 1) on BLOCKED, matching the existing error-path
  convention for other failure modes.

All other commands print to stdout and return exit code 0.

---

## Constraints enforced:
- Output goes to stdout (except BLOCKED path for `go`, which goes to stderr).
- No ANSI color codes (keep output machine-parseable).
- No multi-line output per command (one confirmation line only).

## Non-goals:
- No changes to backing functions (`prd()`, `approve_prd()`, `go()`, etc.).
- No interactive prompts or progress spinners.
- No TUI changes.
- No changes to error output for invalid state or stale execution detection (those already
  print to stderr).

---

## Acceptance criteria (measurable):

1. Running `aiw init` in a test repo produces `ok: initialized .aiw/` on stdout.
2. Running `aiw prd` produces `ok: entered PRD drafting [state: PRD_DRAFT]` on stdout.
3. Running `aiw approve-prd` produces `ok: PRD approved and locked [state: PRD_APPROVED]` on stdout.
4. Running `aiw go TASK-###` (PASS) produces `ok: TASK-### PASS [run_id: ...]` on stdout with
   exit code 0.
5. Running `aiw go TASK-###` (BLOCKED) produces `blocked: TASK-### BLOCKED [run_id: ...]` on
   stderr with exit code 1.
6. Running `aiw decompose` produces `ok: decomposed into N tasks [state: PLANNED]` on stdout.
7. All existing `test_cli_router.py` and `test_cli_state.py` tests pass.
8. New tests in `test_cli_router.py` assert stdout contains the expected confirmation string for
   each command.

## Tests / checks required:
- `pytest tests/test_cli_router.py tests/test_cli_state.py -q`
- `ruff check .`
- `mypy aiw tests`

## Observability requirements:
- None. Stdout output is not a trace event.

## Rollback plan:
- `git checkout` to pre-task baseline.
