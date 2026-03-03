## TASK-026: Decompose AI session and output validation

Type: IMPLEMENTATION
Depends_on: [TASK-008]

Objective:
Implement the AI session invocation for decomposition (single-pass, PCP as context) and the output validator that checks generated artifacts before atomic write.

Context (spec refs):
- PRD §4 (deterministic decomposition outputs)
- SDD §4.1 (spec-phase AI — single-pass, artifact-scoped)

Inputs:
- PCP documents (docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml)
- Decompose orchestration interface (TASK-008)

Outputs (artifacts/files created or changed):
- `aiw/orchestrator/decompose.py` (extended — AI session logic)
- `aiw/orchestrator/decompose_validator.py`
- `tests/test_decompose_validation.py`

File scope allowlist:
- aiw/orchestrator/decompose.py
- aiw/orchestrator/decompose_validator.py
- tests/test_decompose_validation.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:
- `invoke_decompose_session(pcp_paths: dict) -> RawDecomposeOutput`
- `validate_decompose_output(output: RawDecomposeOutput) -> list[str]` — returns validation errors.
- Validation checks:
  - DAG.md exists and non-empty.
  - DAG.yml valid YAML with required schema.
  - At least one TASK-###.md file.
  - Each TASK file has required fields (per TASK template).
- Invalid output causes decompose to abort (no atomic write).

Constraints enforced:
- Spec-phase AI is single-pass (SDD §4.1).

Non-goals:
- No orchestration logic (done in TASK-008).
- No state transitions (done in TASK-008).
- AI prompt quality tuning is out of scope.

Acceptance criteria (measurable):
- AI session invoked with PCP content.
- Valid output passes validation (empty error list).
- Missing DAG.md detected.
- Invalid DAG.yml YAML detected.
- Missing TASK files detected.
- TASK files missing required fields detected.
- Tests use stub/mock AI session.

Tests / checks required:
- `pytest tests/test_decompose_validation.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- Validation errors returned for trace emission by caller.

Rollback plan:
- `git checkout` to pre-task baseline.
