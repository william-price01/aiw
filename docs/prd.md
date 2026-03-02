# PRD: AIW (AI Workflow) – Local AI Coding Orchestrator

## 1. Problem Statement

Brute-force coding with chat-based AI tools (e.g., Claude Code) is fast but inefficient:

- Context resets waste time.
- Iterations are unstructured and difficult to reproduce.
- There are no enforced guardrails (write scope, bounded loops).
- Subagent reasoning is opaque.
- Costs are unpredictable.
- Artifacts (PRD, SDD, tasks) are inconsistent.

AIW is a **local CLI-based AI coding orchestrator** designed for a single advanced developer. It must match or exceed Claude Code in speed while adding structure, reproducibility, visibility, and bounded execution.

It is not a SaaS product. It runs locally inside a git repository.

---

## 2. Target Users

**Primary User:**  
- Single advanced developer (power user).
- Comfortable with CLI.
- Values speed over ceremony.
- Wants deterministic artifacts and tight iteration loops.
- Optimizes for cost and execution velocity.

No multi-user support is required.

---

## 3. User Stories

1. As a developer, I run `aiw` and enter an interactive coding session instantly.
2. As a developer, I run `aiw go TASK-001` and the system executes a bounded patch → test → fix loop automatically.
3. As a developer, I see visible subagent phases (e.g., Planner → Coder → Tester → Fixer).
4. As a developer, I can inspect a structured JSONL trace of what happened.
5. As a developer, each task has a small persistent memory capsule that avoids context bloat.
6. As a developer, AIW enforces write-scope constraints to avoid unsafe modifications.
7. As a developer, the loop stops after N attempts and generates a blocker report.
8. As a developer, I can undo/reset changes quickly.
9. As a developer, I can initialize a new project with spec templates in seconds.
10. As a developer, I spend less money than brute-force chat iteration.

---

## 4. Scope (In)

### 4.1 Local CLI Tool

- Single binary or CLI entrypoint: `aiw`
- Works inside existing git repository
- No web UI
- No server process
- No cloud infra required

---

### 4.2 Project Initialization

Command: `aiw init`

- Creates `.aiw/` directory
- Creates:
  - `.aiw/tasks/`
  - `.aiw/memory/`
  - `.aiw/traces/`
  - `.aiw/templates/`
- Copies prompt templates:
  - PRD agent
  - SDD agent
  - Decomposer agent
  - Constraints agent
- Initializes config file (`aiw.yaml`)
- Validates git repository presence

---

### 4.3 Spec Pipeline

Commands:
- `aiw prd`
- `aiw sdd`
- `aiw decompose`

Capabilities:

- Generate PRD from rough input.
- Generate SDD from PRD.
- Decompose SDD into task DAG.
- Save deterministic artifacts:
  - `docs/prd.md`
  - `docs/sdd.md`
  - `docs/tasks.md`

No architectural overreach beyond local files.

---

### 4.4 Coding Loop (Core)

Command:
- `aiw go TASK-001`

Flow:

1. Load task capsule.
2. Spawn subagents:
   - Planner (optional)
   - Coder (via Codex CLI)
   - Tester
   - Fixer
3. Apply patch.
4. Run tests.
5. Extract failure excerpt (bounded length).
6. Attempt fix.
7. Stop after max N iterations (default: 3).
8. If unresolved → generate blocker report.

Constraints:

- Enforce write-scope (file allowlist from task definition).
- Reject changes outside scope.
- Abort on excessive diff size.

---

### 4.5 Per-Task Capsule Memory

Each task gets:

`.aiw/memory/TASK-001.json`

Contains:

- Summary
- Attempts
- Failures
- Final status
- Key artifacts

Capsule must remain small (e.g., < 10KB target).

Purpose:
- Avoid reloading entire project context.
- Preserve critical state only.

---

### 4.6 Observability

1. Structured event log:
   - `.aiw/traces/run-<timestamp>.jsonl`
   - Each line: structured event
     - agent_spawned
     - patch_applied
     - test_run
     - test_failed
     - fix_attempt
     - blocker

2. Terminal trace view:
   - Tree-style subagent rendering.
   - Clear phase transitions.

3. Diff summary:
   - File list changed
   - +/- line counts

4. Failure excerpt:
   - Truncated to configurable max length.

5. Undo/reset:
   - Git-based reset of last patch.
   - `aiw undo`

---

### 4.7 Cost Awareness

- Track token usage per run.
- Estimate cost per run.
- Abort if cost threshold exceeded.
- Prevent infinite loops via:
  - Max iteration bound
  - Max token bound
  - Max runtime bound

---

### 4.8 Codex CLI Integration

- Coding phase delegates to Codex CLI.
- AIW orchestrates:
  - Prompt injection
  - File scope enforcement
  - Patch validation
  - Iteration management

Codex is replaceable in future, but MVP assumes Codex.

---

## 5. Non-Goals (Out of Scope)

- SaaS architecture
- Web frontend
- Multi-user support
- Persistent remote database
- Microservices
- Plugin marketplace
- CI/CD orchestration
- Autonomous long-running agents
- Background daemons
- Distributed execution

Keep minimal and local-first.

---

## 6. Acceptance Criteria (Measurable)

AIW is successful if:

### Speed & Loop

- `aiw go TASK-001` begins execution in < 1 second.
- Full patch → test → fix loop completes within 2× manual Claude loop time.
- Max iteration bound enforced (default 3).
- No infinite loops possible.

### Determinism

- All runs produce:
  - Trace file
  - Capsule memory
- Re-running same task without code changes yields identical plan phase.

### Guardrails

- Files outside task write-scope are never modified.
- Attempt exceeding diff size threshold aborts.
- Loop halts after N attempts and produces blocker report.

### Observability

- Subagent tree visible in terminal.
- JSONL trace file generated every run.
- Failure excerpt shown and truncated correctly.

### Cost Control

- Token usage recorded.
- Cost estimate displayed.
- Configurable hard cost cap enforced.

### Usability

- Single command interactive mode (`aiw`) works.
- Autopilot mode (`aiw go TASK-001`) works without manual intervention.
- No web interface required.

### Outcome Metric

After 2 weeks of usage:

- Developer subjectively reports faster iteration vs Claude Code alone.
- Measured average task completion time reduced by ≥ 20%.
- Token spend reduced by ≥ 25% vs brute-force iteration baseline.

---

## 7. Technical Assumptions

1. Git is installed and repository is clean before run.
2. Tests are runnable via a standard command (e.g., `pytest`).
3. Codex CLI is available locally.
4. Developer operates on macOS or Linux.
5. Single-threaded orchestration is sufficient for MVP.
6. Terminal supports ANSI rendering for tree output.

---

## 8. Risks

### Risk 1: Added Structure Slows Down Loop
Guardrails may introduce friction.

### Risk 2: Codex Latency Dominates Loop
External CLI may slow iteration.

### Risk 3: Over-Engineering MVP
Too many abstractions reduce speed.

### Risk 4: Context Capsule Insufficient
Too little memory causes repeated failure loops.

### Risk 5: Diff Rejection Frustration
Strict write-scope may block legitimate fixes.

---

## 9. De-risk Strategy

1. Build minimal vertical slice:
   - `aiw go` with bounded loop only.
2. Measure raw loop speed before adding advanced features.
3. Start with simple file-allowlist enforcement.
4. Keep capsule schema minimal and extensible.
5. Add telemetry from day one to measure loop duration and cost.
6. Dogfood exclusively on real tasks.

---

## 10. MVP Milestones

### Milestone 1 – Minimal Loop
- `aiw go TASK-001`
- Patch → test → fix
- Max 3 attempts
- Git-based undo
- Basic terminal output

### Milestone 2 – Guardrails
- Write-scope enforcement
- Diff size cap
- Failure excerpt extraction
- Blocker report generation

### Milestone 3 – Observability
- JSONL trace logging
- Tree-style agent rendering
- Cost tracking

### Milestone 4 – Spec Pipeline
- `aiw prd`
- `aiw sdd`
- `aiw decompose`
- Deterministic artifact generation

---

AIW MVP is complete when:

- It is used daily for real development.
- It replaces brute-force chat iteration.
- It feels faster, not heavier.
- It produces structured, reproducible artifacts without slowing execution.
