"""Top-level `aiw` CLI router and argument parsing."""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final, NoReturn

from aiw.cli.change_request_cmd import request_change
from aiw.cli.decompose_cmd import decompose
from aiw.cli.go_cmd import go
from aiw.cli.init_cmd import init_project
from aiw.cli.spec_cmds import (
    adrs,
    approve_adrs,
    approve_constraints,
    approve_prd,
    approve_sdd,
    constraints,
    prd,
    sdd,
)
from aiw.infra import ConstraintsConfig, load_constraints
from aiw.infra.checkpoint import get_baseline_ref, revert_to_checkpoint
from aiw.workflow.recovery import check_stale_execution, recover_stale_execution

LOGGER: Final[logging.Logger] = logging.getLogger(__name__)
DispatchHandler = Callable[[argparse.Namespace, Path], None]
TASK_PLACEHOLDER: Final[str] = "TASK-###"


class _ArgumentParser(argparse.ArgumentParser):
    """Argument parser that normalizes CLI errors to exit code 1."""

    def error(self, message: str) -> NoReturn:
        self.print_usage()
        self.exit(1, f"{self.prog}: error: {message}\n")


def main(argv: Sequence[str] | None = None, root: Path | None = None) -> int:
    """Parse CLI arguments and dispatch to the selected command handler."""
    parser = _build_parser()
    args_list = list(argv) if argv is not None else None

    try:
        parsed = parser.parse_args(args_list)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1

    repo_root = root if root is not None else Path.cwd()
    constraints = _load_repo_constraints(repo_root)
    if constraints is not None:
        stale_exit_code = _handle_stale_execution(repo_root, constraints)
        if stale_exit_code is not None:
            return stale_exit_code

        validation_error = _validate_command_allowed(parsed, repo_root, constraints)
        if validation_error is not None:
            print(validation_error, file=sys.stderr)
            return 1

    handler = _dispatch_table()[parsed.command]
    LOGGER.info("command_dispatch command=%s", parsed.command)
    try:
        handler(parsed, repo_root)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="aiw",
        description="AIW CLI entry point.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_simple_command(subparsers, "init", "Initialize AIW internal state.")
    _add_simple_command(subparsers, "prd", "Enter PRD drafting.")
    _add_simple_command(subparsers, "approve-prd", "Approve the PRD.")
    _add_simple_command(subparsers, "sdd", "Enter SDD drafting.")
    _add_simple_command(subparsers, "approve-sdd", "Approve the SDD.")
    _add_simple_command(subparsers, "adrs", "Enter ADR drafting.")
    _add_simple_command(subparsers, "approve-adrs", "Approve ADRs.")
    _add_simple_command(
        subparsers,
        "constraints",
        "Enter constraints drafting.",
    )
    _add_simple_command(
        subparsers,
        "approve-constraints",
        "Approve constraints.",
    )
    _add_simple_command(subparsers, "decompose", "Generate task decomposition.")
    _add_simple_command(subparsers, "undo", "Revert to the most recent checkpoint.")

    go_parser = subparsers.add_parser(
        "go",
        help="Execute a task.",
        description="Execute a task by task id.",
    )
    go_parser.add_argument("task_id", help="Task identifier, for example TASK-021.")

    reset_parser = subparsers.add_parser(
        "reset",
        help="Reset to a task baseline checkpoint.",
        description="Reset the repository to a task baseline checkpoint.",
    )
    reset_parser.add_argument(
        "task_id",
        help="Task identifier, for example TASK-021.",
    )

    request_change_parser = subparsers.add_parser(
        "request-change",
        help="Create a change request.",
        description="Create a change request for a locked artifact.",
    )
    request_change_parser.add_argument(
        "target",
        help="Locked artifact path that needs modification.",
    )
    request_change_parser.add_argument(
        "--reason",
        required=True,
        help="Reason the locked artifact must change.",
    )
    request_change_parser.add_argument(
        "--impact",
        required=True,
        help="Impact of the requested change.",
    )

    return parser


def _add_simple_command(
    subparsers: Any,
    name: str,
    description: str,
) -> None:
    subparsers.add_parser(
        name,
        help=description,
        description=description,
    )


def _dispatch_table() -> dict[str, DispatchHandler]:
    return {
        "init": _dispatch_init,
        "prd": _dispatch_prd,
        "approve-prd": _dispatch_approve_prd,
        "sdd": _dispatch_sdd,
        "approve-sdd": _dispatch_approve_sdd,
        "adrs": _dispatch_adrs,
        "approve-adrs": _dispatch_approve_adrs,
        "constraints": _dispatch_constraints,
        "approve-constraints": _dispatch_approve_constraints,
        "decompose": _dispatch_decompose,
        "go": _dispatch_go,
        "undo": _dispatch_undo,
        "reset": _dispatch_reset,
        "request-change": _dispatch_request_change,
    }


def _dispatch_init(_: argparse.Namespace, root: Path) -> None:
    init_project(root)
    print("ok: initialized .aiw/ [state: INIT]")


def _dispatch_prd(_: argparse.Namespace, root: Path) -> None:
    session = prd(root)
    print(f"ok: entered PRD drafting [state: {_result_state(session, 'PRD_DRAFT')}]")


def _dispatch_approve_prd(_: argparse.Namespace, root: Path) -> None:
    result = approve_prd(root)
    print(
        "ok: PRD approved and locked "
        f"[state: {_result_state(result, 'PRD_APPROVED')}]"
    )


def _dispatch_sdd(_: argparse.Namespace, root: Path) -> None:
    session = sdd(root)
    print(f"ok: entered SDD drafting [state: {_result_state(session, 'SDD_DRAFT')}]")


def _dispatch_approve_sdd(_: argparse.Namespace, root: Path) -> None:
    result = approve_sdd(root)
    print(
        "ok: SDD approved and locked "
        f"[state: {_result_state(result, 'SDD_APPROVED')}]"
    )


def _dispatch_adrs(_: argparse.Namespace, root: Path) -> None:
    session = adrs(root)
    print(
        f"ok: entered ADR drafting [state: {_result_state(session, 'ADRS_DRAFT')}]"
    )


def _dispatch_approve_adrs(_: argparse.Namespace, root: Path) -> None:
    result = approve_adrs(root)
    print(
        "ok: ADRs approved and locked "
        f"[state: {_result_state(result, 'ADRS_APPROVED')}]"
    )


def _dispatch_constraints(_: argparse.Namespace, root: Path) -> None:
    session = constraints(root)
    print(
        "ok: entered constraints drafting "
        f"[state: {_result_state(session, 'CONSTRAINTS_DRAFT')}]"
    )


def _dispatch_approve_constraints(_: argparse.Namespace, root: Path) -> None:
    result = approve_constraints(root)
    print(
        "ok: constraints approved and locked "
        f"[state: {_result_state(result, 'CONSTRAINTS_APPROVED')}]"
    )


def _dispatch_decompose(_: argparse.Namespace, root: Path) -> None:
    result = decompose(root)
    task_count = sum(
        1
        for path in getattr(result, "written_files", ())
        if Path(path).name.startswith("TASK-")
    )
    print(
        "ok: decomposed into "
        f"{task_count} tasks [state: {_result_state(result, 'PLANNED')}]"
    )


def _dispatch_go(args: argparse.Namespace, root: Path) -> None:
    result = go(root, args.task_id)
    status = getattr(result, "status", None)
    run_id = getattr(result, "run_id", None)
    if not isinstance(status, str) or not isinstance(run_id, str):
        return
    status_line = f"{args.task_id} {status} [run_id: {run_id}]"
    if status == "BLOCKED":
        print(f"blocked: {status_line}", file=sys.stderr)
        raise SystemExit(1)
    print(f"ok: {status_line}")


def _dispatch_undo(_: argparse.Namespace, root: Path) -> None:
    undo(root)
    print("ok: reverted to last checkpoint")


def _dispatch_reset(args: argparse.Namespace, root: Path) -> None:
    reset(root, args.task_id)
    print(f"ok: reset to {args.task_id} baseline")


def _dispatch_request_change(args: argparse.Namespace, root: Path) -> None:
    request_change(
        root,
        target=args.target,
        reason=args.reason,
        impact=args.impact,
    )
    print("ok: change request written to docs/requests/CHANGE_REQUEST.md")


def _load_repo_constraints(root: Path) -> ConstraintsConfig | None:
    constraints_path = root / "docs" / "constraints.yml"
    if not constraints_path.exists():
        return None
    return load_constraints(constraints_path)


def _handle_stale_execution(root: Path, constraints: ConstraintsConfig) -> int | None:
    state_path = root / constraints.workflow.state_file
    if not state_path.exists():
        return None
    if not check_stale_execution(state_path):
        return None

    recover_stale_execution(state_path)
    _sync_legacy_state_field(state_path)
    message = (
        "stale EXECUTING state detected; transitioned workflow to BLOCKED. "
        "Resolve manually before re-running."
    )
    LOGGER.error("stale_execution_blocked state_path=%s", state_path)
    print(message, file=sys.stderr)
    return 1


def _validate_command_allowed(
    parsed: argparse.Namespace,
    root: Path,
    constraints: ConstraintsConfig,
) -> str | None:
    state_path = root / constraints.workflow.state_file
    current_state = _read_current_state(state_path)
    command = _canonical_command(parsed)
    allowed_commands = constraints.workflow.allowed_commands_by_state.get(
        current_state,
        [],
    )
    if command in allowed_commands:
        return None

    allowed_text = ", ".join(allowed_commands) if allowed_commands else "(none)"
    message = (
        f"Command {command!r} is not allowed in state {current_state!r}. "
        f"Allowed commands: {allowed_text}"
    )
    LOGGER.error(
        "state_validation_failed state=%s command=%s allowed=%s",
        current_state,
        command,
        allowed_commands,
    )
    return message


def _read_current_state(state_path: Path) -> str:
    if not state_path.exists():
        return "INIT"

    data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("workflow state file must contain a JSON object")
    for key in ("current_state", "state"):
        value = data.get(key)
        if isinstance(value, str):
            return value

    raise ValueError(
        "workflow state file missing string field 'current_state' or 'state'"
    )


def _result_state(result: object, fallback: str) -> str:
    state = getattr(result, "state", None)
    return state if isinstance(state, str) else fallback


def _sync_legacy_state_field(state_path: Path) -> None:
    data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("workflow state file must contain a JSON object")
    current_state = data.get("current_state")
    if not isinstance(current_state, str):
        raise ValueError("workflow state file missing string field 'current_state'")
    if data.get("state") == current_state:
        return
    data["state"] = current_state
    state_path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _canonical_command(parsed: argparse.Namespace) -> str:
    if parsed.command == "go":
        return f"aiw go {TASK_PLACEHOLDER}"
    if parsed.command == "reset":
        return f"aiw reset {TASK_PLACEHOLDER}"
    return f"aiw {parsed.command}"


def undo(root: Path) -> None:
    """Revert the repository to the most recent AIW checkpoint commit."""
    with _pushd(root):
        checkpoint_ref = _latest_checkpoint_ref()
        revert_to_checkpoint(checkpoint_ref)


def reset(root: Path, task_id: str) -> None:
    """Reset the repository to the baseline checkpoint for a task."""
    with _pushd(root):
        revert_to_checkpoint(get_baseline_ref(task_id))


def _latest_checkpoint_ref() -> str:
    completed = subprocess.run(
        (
            "git",
            "log",
            "-1",
            "--format=%H",
            "--grep=^\\[aiw-checkpoint\\] ",
        ),
        check=True,
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    checkpoint_ref = completed.stdout.strip()
    if not checkpoint_ref:
        raise RuntimeError("no checkpoint commit found")
    return checkpoint_ref


@contextmanager
def _pushd(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)
