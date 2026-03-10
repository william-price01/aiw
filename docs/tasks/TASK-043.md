## TASK-043: Session capture — pty-based Codex subprocess wrapper

Type: IMPLEMENTATION
Depends_on: [TASK-038]

Objective:
Implement a pty-based subprocess wrapper (`SessionCapture`) that spawns Codex CLI invocations
via a pseudo-terminal, streams output to a persisted session log file and an in-memory buffer
simultaneously, and exposes the read path for live SSE streaming. Wire the executor's Coder and
Fixer session spawning to use `SessionCapture` instead of plain subprocess. Session log files
are written to `.aiw/runs/` alongside the JSONL trace.

Context (spec refs):
- PRD §15.3.1 (Session Visibility)
- SDD §19.2.1 (Session Capture Architecture)

Inputs:
- `aiw/orchestrator/coder.py` (Coder session — currently spawns Codex via subprocess)
- `.aiw/runs/` directory (session log output location)

Outputs (artifacts/files created or changed):
- `aiw/infra/session_capture.py`
- `aiw/orchestrator/coder.py` (swap subprocess call to SessionCapture)
- `tests/test_session_capture.py`

File scope allowlist:
- aiw/infra/session_capture.py
- aiw/orchestrator/coder.py
- tests/test_session_capture.py

Locked artifacts confirmation:
- Confirm: will NOT edit docs/prd.md, docs/sdd.md, docs/adrs/**, docs/constraints.yml

Interfaces/contracts:

`SessionCapture`:
```python
class SessionCapture:
    def __init__(
        self,
        cmd: list[str],
        log_path: Path,
        env: dict | None = None,
    ) -> None: ...

    def run(self) -> int:
        """
        Spawn the command via pty. Stream all output to:
          1. log_path (append-only, written in real time)
          2. self._buffer (in-memory deque, capped at 10MB)
        Block until process exits. Return exit code.
        """

    @property
    def pid(self) -> int | None:
        """PID of the spawned process. None before run() is called."""

    def read_log(self) -> str:
        """Return full contents of log_path as a string."""

    def is_active(self) -> bool:
        """True if the process is still running."""

    # Forward-compatible hook — NOT implemented for MVP.
    # Exists so the interactive input path can be added without
    # replacing this class. For MVP, calling this raises NotImplementedError.
    def write_stdin(self, data: bytes) -> None:
        raise NotImplementedError("Interactive input not supported in MVP")
```

Session log file naming:
- Coder: `.aiw/runs/session-<run_id>-coder.log`
- `run_id` is the UUID already stored in `workflow_state.json` at EXECUTING entry.

Pty implementation:
- Use `ptyprocess.PtyProcess` (from the `ptyprocess` package) for cross-platform pty management.
- Fallback: `os.openpty()` + `subprocess.Popen` with `stdin/stdout/stderr` bound to the pty fd (Linux/macOS only).
- `ptyprocess` is preferred — it handles SIGWINCH, EOF, and process reaping correctly.
- Windows is not supported; raise `PlatformNotSupportedError` on `sys.platform == "win32"`.

Executor integration:
- `coder.py`: replace the Codex subprocess invocation with `SessionCapture(cmd, log_path).run()`.
- The `run_id` must be passed into Coder from the executor so the log file can be named correctly. Add `run_id: str` parameter to `run_coder_session()` signature.
- No other changes to coder.py logic.
- Existing `PatchResult` return contract is unchanged.

Output capture:
- All bytes read from the pty fd are written to the log file immediately (unbuffered).
- The in-memory buffer (`_buffer: collections.deque[bytes]`) holds the same bytes, capped at 10MB total. Oldest bytes are dropped when cap is exceeded.
- The buffer is used by the SSE tail loop in the Canvas API server (TASK-040) to push chunks to connected clients.

Error handling:
- If the pty spawn fails: raise `SessionCaptureError` with the underlying OS error.
- If the log directory (`.aiw/runs/`) does not exist: create it before opening the log file.
- Process non-zero exit code is returned from `run()` and handled by the caller (coder/fixer) as before.

Constraints enforced:
- Session log files written to `.aiw/runs/` only.
- Coding agents must not write to `.aiw/**` directly — this constraint applies to the Codex subprocess, not to AIW's own infrastructure code. `SessionCapture` is AIW infrastructure and is permitted to write session logs to `.aiw/runs/`.
- `write_stdin()` raises `NotImplementedError` in MVP — no interactive input path.
- No changes to execution logic, patch validation, or test-running behavior.

Non-goals:
- No interactive input to sessions (MVP is read-only; `write_stdin` is a stub only).
- No Windows pty support.
- No session log rotation or cleanup (operator manages `.aiw/runs/` size).
- No changes to PatchResult, scope validation, or test execution.
- No Canvas API server changes (done in TASK-040, which depends on this task).

Acceptance criteria (measurable):
1. `SessionCapture(cmd, log_path).run()` spawns the command via pty and returns its exit code.
2. All process output appears in `log_path` after `run()` completes.
3. `SessionCapture.read_log()` returns the same content as `log_path`.
4. `SessionCapture.is_active()` returns True during execution and False after.
5. `SessionCapture.write_stdin()` raises `NotImplementedError`.
6. `run_coder_session(task_spec, constraints, run_id=...)` writes `.aiw/runs/session-<run_id>-coder.log`.
7. Existing `test_coder.py` tests continue to pass.
9. On `sys.platform == "win32"`: `SessionCapture` raises `PlatformNotSupportedError` at instantiation.
10. Buffer cap: when output exceeds 10MB, oldest bytes are dropped without error.

Tests / checks required:
- `pytest tests/test_session_capture.py tests/test_coder.py -q`
- `ruff check .`
- `mypy aiw tests`

Observability requirements:
- No new JSONL trace events. Session log files are the observability artifact.

Rollback plan:
- `git checkout` to pre-task baseline.
