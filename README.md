# AIW

AIW is a local, spec-locked AI coding orchestrator for a single repository. It enforces an explicit workflow state machine, keeps planning artifacts in versioned docs, and runs bounded task execution with deterministic termination (`PASS` or `BLOCKED`).

The product direction comes from [docs/prd.md](/home/williamprice/aiw-dev-task-016/docs/prd.md) and [docs/sdd.md](/home/williamprice/aiw-dev-task-016/docs/sdd.md). This repository currently implements the workflow scaffolding, constraints model, task execution loop, checkpointing, and CLI surface for that design.

## What AIW is for

- Locking work to authoritative artifacts: PRD, SDD, ADRs, constraints, and task specs.
- Enforcing workflow progression through `.aiw/workflow_state.json`.
- Running one task at a time with a bounded Coder/Fixer loop.
- Recording task completion and structured JSONL traces for inspection.
- Keeping execution deterministic and repo-local rather than chat-driven.

## Current status

Implemented today:

- `aiw init` scaffold creation
- Spec-phase state transitions: `prd`, `sdd`, `adrs`, `constraints`, and approval commands
- Constraint loading and gate validation
- Task linting and file-scope validation
- Bounded execution orchestration for `aiw go TASK-###`
- Git checkpoint creation, `aiw undo`, and `aiw reset TASK-###`
- Change request file generation and re-approval rollback

Not fully wired yet:

- `aiw decompose` validates state and output shape, but the bounded AI session is still a stub and currently raises `NotImplementedError`
- Coder/Fixer execution expects the `codex` CLI to be available for live AI patch generation

## Repository layout

```text
aiw/
  cli/             CLI entry points
  orchestrator/    decompose, execution, coder, fixer orchestration
  workflow/        state machine, locking, gates, change requests
  infra/           constraints, checkpoints, traces, layer checks
  tasks/           task linting and scope validation
docs/
  prd.md
  sdd.md
  constraints.yml
  adrs/
  tasks/
tests/
```

Internal runtime state lives under `.aiw/` and is owned by AIW.

## Installation

AIW targets Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Or with `uv`:

```bash
uv sync --extra dev
```

## CLI

```bash
aiw init
aiw prd
aiw approve-prd
aiw sdd
aiw approve-sdd
aiw adrs
aiw approve-adrs
aiw constraints
aiw approve-constraints
aiw decompose
aiw go TASK-### 
aiw undo
aiw reset TASK-###
aiw request-change <target> --reason "..." --impact "..."
```

## Workflow

AIW enforces this state progression:

```text
INIT
-> PRD_DRAFT -> PRD_APPROVED
-> SDD_DRAFT -> SDD_APPROVED
-> ADRS_DRAFT -> ADRS_APPROVED
-> CONSTRAINTS_DRAFT -> CONSTRAINTS_APPROVED
-> PLANNED
-> EXECUTING
-> PLANNED | BLOCKED
```

Authoritative state is stored in `.aiw/workflow_state.json`.

Locked artifact rules come from [docs/constraints.yml](/home/williamprice/aiw-dev-task-016/docs/constraints.yml):

- `docs/prd.md` locks after `PRD_APPROVED`
- `docs/sdd.md` locks after `SDD_APPROVED`
- `docs/adrs/**` locks after `ADRS_APPROVED`
- `docs/constraints.yml` locks after `CONSTRAINTS_APPROVED`
- During execution, task planning artifacts are immutable except append-only updates to `docs/tasks/COMPLETED.md`

If downstream work requires editing a locked artifact, create a change request with `aiw request-change`.

## Typical usage

```bash
aiw init
aiw prd
# edit docs/prd.md
aiw approve-prd

aiw sdd
# edit docs/sdd.md
aiw approve-sdd

aiw adrs
# edit docs/adrs/*
aiw approve-adrs

aiw constraints
# edit docs/constraints.yml
aiw approve-constraints

# planned task generation is designed to happen here
aiw decompose

# once docs/tasks/TASK-###.md exists and state is PLANNED
aiw go TASK-015
```

## Execution behavior

`aiw go TASK-###` does the following:

1. Loads and validates constraints.
2. Requires workflow state `PLANNED`.
3. Lints the selected task file and enforces its file-scope allowlist.
4. Creates a git baseline checkpoint.
5. Runs one Coder pass.
6. Runs the configured test command from [docs/constraints.yml](/home/williamprice/aiw-dev-task-016/docs/constraints.yml).
7. If tests fail, runs one Fixer pass and re-tests.
8. Terminates deterministically as `PASS` or `BLOCKED`.

On success, AIW appends a record to `docs/tasks/COMPLETED.md` and emits a JSONL trace under `.aiw/runs/`.

## Development

Run the test suite:

```bash
pytest -q
```

Optional local checks:

```bash
ruff check .
mypy aiw tests
```

## Notes for contributors

- Prefer updating the spec artifacts in `docs/` before changing orchestration behavior.
- Keep the README aligned with the implemented CLI, not only the PRD target state.
- Do not treat `.aiw/` as user-authored content.
