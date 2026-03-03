## TASK-022: Layer import boundary enforcement

Type: IMPLEMENTATION
Depends_on: [TASK-003]

Objective:
Implement static analysis that validates Python imports respect the layer boundaries defined in constraints.yml.

Context (spec refs):
- constraints.yml: `layers` (cli→orchestrator→workflow→tasks→infra)
- SDD §11 (constraint enforcement — layering/import boundaries)

Inputs:
- constraints.yml layer definitions
- Python source files in aiw/

Outputs (artifacts/files created or changed):
- `aiw/infra/layer_check.py`
- `tests/test_layer_check.py`

File scope allowlist:
- aiw/infra/layer_check.py
- tests/test_layer_check.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `check_layer_boundaries(source_dir: Path, constraints: ConstraintsConfig) -> list[str]` — returns violations.
- Parses import statements from Python files.
- Validates against allowed_imports per layer.

Constraints enforced:
- `layers[*].allowed_imports`

Non-goals:
- No runtime enforcement (static check only).
- No auto-fix.

Acceptance criteria (measurable):
- cli importing orchestrator: allowed.
- cli importing workflow: allowed.
- infra importing cli: violation detected.
- tasks importing orchestrator: violation detected.
- Returns structured violation list.

Tests / checks required:
- `pytest tests/test_layer_check.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- None (static analysis tool).

Rollback plan:
- `git checkout` to pre-task baseline.
