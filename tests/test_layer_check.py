"""Tests for static layer-boundary import validation."""

from __future__ import annotations

from pathlib import Path

from aiw.infra.constraints import load_constraints
from aiw.infra.layer_check import check_layer_boundaries


def test_check_layer_boundaries_allows_configured_forward_imports(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "aiw"
    _write_python(
        source_dir / "cli" / "entry.py",
        "import aiw.orchestrator\nfrom aiw.workflow import state_machine\n",
    )

    violations = check_layer_boundaries(
        source_dir, load_constraints(Path("docs/constraints.yml"))
    )

    assert violations == []


def test_check_layer_boundaries_detects_disallowed_cross_layer_imports(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "aiw"
    _write_python(source_dir / "infra" / "bad.py", "import aiw.cli\n")
    _write_python(
        source_dir / "tasks" / "bad.py",
        "from ..orchestrator import coordinator\n",
    )

    violations = check_layer_boundaries(
        source_dir, load_constraints(Path("docs/constraints.yml"))
    )

    assert violations == [
        f"{(source_dir / 'infra' / 'bad.py').as_posix()}:1: "
        "infra may not import cli (import aiw.cli)",
        f"{(source_dir / 'tasks' / 'bad.py').as_posix()}:1: "
        "tasks may not import orchestrator (from ..orchestrator import ...)",
    ]


def test_check_layer_boundaries_ignores_external_and_same_layer_imports(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "aiw"
    _write_python(
        source_dir / "workflow" / "local.py",
        "import json\nfrom . import helpers\nfrom .helpers import run\n",
    )
    _write_python(source_dir / "workflow" / "helpers.py", "VALUE = 1\n")

    violations = check_layer_boundaries(
        source_dir, load_constraints(Path("docs/constraints.yml"))
    )

    assert violations == []


def _write_python(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
