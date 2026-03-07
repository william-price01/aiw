"""Top-level `aiw` CLI router and argument parsing."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
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
from aiw.infra.checkpoint import get_baseline_ref, revert_to_checkpoint

LOGGER: Final[logging.Logger] = logging.getLogger(__name__)
DispatchHandler = Callable[[argparse.Namespace, Path], None]


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
    handler = _dispatch_table()[parsed.command]
    LOGGER.info("command_dispatch command=%s", parsed.command)
    handler(parsed, repo_root)
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


def _dispatch_prd(_: argparse.Namespace, root: Path) -> None:
    prd(root)


def _dispatch_approve_prd(_: argparse.Namespace, root: Path) -> None:
    approve_prd(root)


def _dispatch_sdd(_: argparse.Namespace, root: Path) -> None:
    sdd(root)


def _dispatch_approve_sdd(_: argparse.Namespace, root: Path) -> None:
    approve_sdd(root)


def _dispatch_adrs(_: argparse.Namespace, root: Path) -> None:
    adrs(root)


def _dispatch_approve_adrs(_: argparse.Namespace, root: Path) -> None:
    approve_adrs(root)


def _dispatch_constraints(_: argparse.Namespace, root: Path) -> None:
    constraints(root)


def _dispatch_approve_constraints(_: argparse.Namespace, root: Path) -> None:
    approve_constraints(root)


def _dispatch_decompose(_: argparse.Namespace, root: Path) -> None:
    decompose(root)


def _dispatch_go(args: argparse.Namespace, root: Path) -> None:
    go(root, args.task_id)


def _dispatch_undo(_: argparse.Namespace, root: Path) -> None:
    undo(root)


def _dispatch_reset(args: argparse.Namespace, root: Path) -> None:
    reset(root, args.task_id)


def _dispatch_request_change(args: argparse.Namespace, root: Path) -> None:
    request_change(
        root,
        target=args.target,
        reason=args.reason,
        impact=args.impact,
    )


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
