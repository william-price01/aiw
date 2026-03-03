"""Tests for constraints loader and validation."""

from __future__ import annotations

from pathlib import Path

from aiw.infra import load_constraints, validate_constraints


def test_load_constraints_returns_typed_sections() -> None:
    config = load_constraints(Path("docs/constraints.yml"))

    assert config.project.name == "aiw"
    assert config.layers[0].name == "cli"
    assert config.boundaries.internal_tool_state.writer == "aiw_only"
    assert config.quality.test_command == "`pytest -q`"
    assert (
        config.execution.constraints_finalization_gate.required_non_placeholder_fields
        == ["quality.test_command"]
    )


def test_validate_constraints_returns_no_errors_for_valid_file() -> None:
    config = load_constraints(Path("docs/constraints.yml"))

    assert validate_constraints(config) == []


def test_validate_constraints_detects_missing_quality_test_command(
    tmp_path: Path,
) -> None:
    content = _replace_test_command_line(_constraints_text(), "")

    config = load_constraints(_write_constraints(tmp_path, content))
    errors = validate_constraints(config)

    assert "Missing required field: quality.test_command" in errors


def test_validate_constraints_detects_tbd_placeholder(tmp_path: Path) -> None:
    content = _replace_test_command_line(_constraints_text(), '  test_command: "TBD"')

    config = load_constraints(_write_constraints(tmp_path, content))
    errors = validate_constraints(config)

    assert "Field quality.test_command contains placeholder value: 'TBD'" in errors


def test_validate_constraints_detects_empty_placeholder(tmp_path: Path) -> None:
    content = _replace_test_command_line(_constraints_text(), '  test_command: ""')

    config = load_constraints(_write_constraints(tmp_path, content))
    errors = validate_constraints(config)

    assert "Field quality.test_command contains placeholder value: ''" in errors


def _constraints_text() -> str:
    return Path("docs/constraints.yml").read_text(encoding="utf-8")


def _replace_test_command_line(content: str, replacement: str) -> str:
    needle = "  test_command: `pytest -q`"
    if needle not in content:
        raise AssertionError("expected baseline test_command line in constraints file")
    return content.replace(needle, replacement, 1)


def _write_constraints(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "constraints.yml"
    path.write_text(content, encoding="utf-8")
    return path
