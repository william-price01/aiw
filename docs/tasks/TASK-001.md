## TASK-001: Project scaffold and package layout

Type: IMPLEMENTATION
Depends_on: []

Objective:
Create the Python package structure for AIW with layer-separated modules matching the constraints.yml layer definitions.

Context (spec refs):
- PRD §4 (scope), §16 (file structure)
- SDD §1 (system overview)
- constraints.yml: `project.stack`, `layers`

Inputs:
- constraints.yml layer definitions (cli, orchestrator, workflow, tasks, infra)

Outputs (artifacts/files created or changed):
- `pyproject.toml` with project metadata and dependencies
- `aiw/__init__.py`
- `aiw/cli/__init__.py`
- `aiw/orchestrator/__init__.py`
- `aiw/workflow/__init__.py`
- `aiw/tasks/__init__.py`
- `aiw/infra/__init__.py`
- `tests/__init__.py`

File scope allowlist:
- aiw/**/__init__.py
- pyproject.toml
- setup.cfg
- tests/__init__.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- Each layer module exposes `__init__.py` for clean imports.

Constraints enforced:
- `project.stack`: Python 3.10+
- `layers`: cli, orchestrator, workflow, tasks, infra

Non-goals:
- No business logic in this task.
- No CLI commands.
- No tests beyond importability.

Acceptance criteria (measurable):
- `python -c "import aiw"` succeeds.
- `python -c "import aiw.cli; import aiw.orchestrator; import aiw.workflow; import aiw.tasks; import aiw.infra"` succeeds.
- `ruff check .` passes.
- `mypy aiw tests` passes.

Tests / checks required:
- `python -c "import aiw"`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- None (no runtime behavior).

Rollback plan:
- `git checkout` to pre-task baseline.
