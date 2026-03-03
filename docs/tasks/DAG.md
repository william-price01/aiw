# DAG: AIW Decomposition

## Topological Order

| Task | Title | Type | Depends On |
|------|-------|------|------------|
| TASK-001 | Project scaffold and package layout | IMPLEMENTATION | — |
| TASK-002 | Workflow state machine (core) | IMPLEMENTATION | TASK-001 |
| TASK-003 | Constraints loader and validator | IMPLEMENTATION | TASK-001 |
| TASK-004 | Artifact locking engine | IMPLEMENTATION | TASK-002 |
| TASK-005 | `aiw init` command | IMPLEMENTATION | TASK-002 |
| TASK-006 | Spec-phase draft commands (prd/sdd/adrs/constraints) | IMPLEMENTATION | TASK-004, TASK-005 |
| TASK-025 | Spec-phase approve commands (approve-prd/sdd/adrs/constraints) | IMPLEMENTATION | TASK-006 |
| TASK-007 | Constraints finalization gate | IMPLEMENTATION | TASK-003, TASK-025 |
| TASK-008 | Decompose orchestration and atomic write | IMPLEMENTATION | TASK-007 |
| TASK-026 | Decompose AI session and output validation | IMPLEMENTATION | TASK-008 |
| TASK-009 | Task lint preflight gate | IMPLEMENTATION | TASK-003, TASK-026 |
| TASK-010 | Observability — JSONL trace emitter | IMPLEMENTATION | TASK-002 |
| TASK-011 | Checkpointing (git-based) | IMPLEMENTATION | TASK-002 |
| TASK-012 | Write-scope and diff validation | IMPLEMENTATION | TASK-003, TASK-004 |
| TASK-013 | Coder session integration | IMPLEMENTATION | TASK-009, TASK-010, TASK-011, TASK-012 |
| TASK-014 | Fixer session integration | IMPLEMENTATION | TASK-013 |
| TASK-015 | Execution loop — happy path (Coder → PASS) | IMPLEMENTATION | TASK-013, TASK-014 |
| TASK-027 | Execution loop — Fixer path, iteration cap, BLOCKED | IMPLEMENTATION | TASK-015 |
| TASK-016 | Blocker report and BLOCKED transition | IMPLEMENTATION | TASK-027 |
| TASK-017 | Undo and reset commands | IMPLEMENTATION | TASK-011, TASK-027 |
| TASK-018 | Stale EXECUTING recovery | IMPLEMENTATION | TASK-002, TASK-027 |
| TASK-019 | Change request flow | IMPLEMENTATION | TASK-004, TASK-025 |
| TASK-020 | Capsule log writer (append-only) | IMPLEMENTATION | TASK-027 |
| TASK-021 | CLI entry point — router and arg parsing | IMPLEMENTATION | TASK-005, TASK-025, TASK-007, TASK-026, TASK-027, TASK-017, TASK-019 |
| TASK-028 | CLI entry point — state validation and stale check | IMPLEMENTATION | TASK-021, TASK-018 |
| TASK-022 | Layer import boundary enforcement | IMPLEMENTATION | TASK-003 |
| TASK-023 | Integration tests — happy path | TESTING | TASK-028 |
| TASK-029 | Integration tests — error and BLOCKED paths | TESTING | TASK-023 |
| TASK-024 | TUI rendering model | IMPLEMENTATION | TASK-028 |

---

## Layered View (Parallelizable Layers)

### Layer 0 — Foundation
- TASK-001: Project scaffold and package layout

### Layer 1 — Core State + Config
- TASK-002: Workflow state machine (core)
- TASK-003: Constraints loader and validator

### Layer 2 — Enforcement Primitives
- TASK-004: Artifact locking engine
- TASK-005: `aiw init` command
- TASK-010: Observability — JSONL trace emitter
- TASK-011: Checkpointing (git-based)
- TASK-022: Layer import boundary enforcement

### Layer 3 — Spec-Phase Draft Commands
- TASK-006: Spec-phase draft commands
- TASK-012: Write-scope and diff validation

### Layer 4 — Spec-Phase Approve + Change Request
- TASK-025: Spec-phase approve commands
- TASK-019: Change request flow

### Layer 5 — Planning Gates
- TASK-007: Constraints finalization gate

### Layer 6 — Decomposition
- TASK-008: Decompose orchestration and atomic write
- TASK-026: Decompose AI session and output validation

### Layer 7 — Execution Preflight
- TASK-009: Task lint preflight gate

### Layer 8 — Execution Core
- TASK-013: Coder session integration
- TASK-014: Fixer session integration

### Layer 9 — Execution Happy Path
- TASK-015: Execution loop — happy path (Coder → PASS)

### Layer 10 — Execution Fixer + BLOCKED
- TASK-027: Execution loop — Fixer path, iteration cap, BLOCKED

### Layer 11 — Execution Support
- TASK-016: Blocker report and BLOCKED transition
- TASK-017: Undo and reset commands
- TASK-018: Stale EXECUTING recovery
- TASK-020: Capsule log writer (append-only)

### Layer 12 — CLI Surface
- TASK-021: CLI entry point — router and arg parsing
- TASK-028: CLI entry point — state validation and stale check

### Layer 13 — Verification + UI
- TASK-023: Integration tests — happy path
- TASK-029: Integration tests — error and BLOCKED paths
- TASK-024: TUI rendering model
