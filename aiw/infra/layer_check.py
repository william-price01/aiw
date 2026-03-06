"""Static layer-boundary validation for AIW Python imports."""

from __future__ import annotations

import ast
from pathlib import Path

from aiw.infra.constraints import ConstraintsConfig


def check_layer_boundaries(
    source_dir: Path, constraints: ConstraintsConfig
) -> list[str]:
    """Return import-boundary violations for Python files under ``source_dir``."""
    known_layers = {layer.name for layer in constraints.layers}
    allowed_imports = {
        layer.name: set(layer.allowed_imports) | {layer.name}
        for layer in constraints.layers
    }
    violations: list[str] = []

    for path in sorted(source_dir.rglob("*.py")):
        current_layer = _current_layer(source_dir, path, known_layers)
        if current_layer is None:
            continue

        module_parts = _module_parts(source_dir, path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for target_layer, line_number, import_text in _iter_import_layers(
            tree, module_parts, known_layers
        ):
            if target_layer in allowed_imports[current_layer]:
                continue
            violations.append(
                f"{path.as_posix()}:{line_number}: "
                f"{current_layer} may not import {target_layer} ({import_text})"
            )

    return violations


def _current_layer(source_dir: Path, path: Path, known_layers: set[str]) -> str | None:
    relative_parts = path.relative_to(source_dir).parts
    if not relative_parts:
        return None
    layer = relative_parts[0]
    if layer not in known_layers:
        return None
    return layer


def _module_parts(source_dir: Path, path: Path) -> tuple[str, ...]:
    relative_path = path.relative_to(source_dir)
    parts = list(relative_path.parts)
    parts[-1] = path.stem
    if parts[-1] == "__init__":
        parts.pop()
    return ("aiw", *parts)


def _iter_import_layers(
    tree: ast.AST, module_parts: tuple[str, ...], known_layers: set[str]
) -> list[tuple[str, int, str]]:
    imports: list[tuple[str, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target_layer = _layer_from_absolute_name(alias.name, known_layers)
                if target_layer is None:
                    continue
                imports.append(
                    (target_layer, node.lineno, f"import {alias.name}")
                )
        elif isinstance(node, ast.ImportFrom):
            target_layer = _layer_from_import_from(node, module_parts, known_layers)
            if target_layer is None:
                continue
            module_name = "." * node.level + (node.module or "")
            imports.append(
                (target_layer, node.lineno, f"from {module_name} import ...")
            )
    return imports


def _layer_from_import_from(
    node: ast.ImportFrom, module_parts: tuple[str, ...], known_layers: set[str]
) -> str | None:
    if node.level == 0:
        return _layer_from_absolute_name(node.module, known_layers)

    package_parts = list(module_parts)
    if path_name := module_parts[-1]:
        if path_name not in known_layers:
            package_parts.pop()

    keep_parts = len(package_parts) - (node.level - 1)
    if keep_parts <= 0:
        return None

    resolved_parts = package_parts[:keep_parts]
    if node.module:
        resolved_parts.extend(node.module.split("."))
    return _layer_from_parts(resolved_parts, known_layers)


def _layer_from_absolute_name(name: str | None, known_layers: set[str]) -> str | None:
    if not name:
        return None
    return _layer_from_parts(name.split("."), known_layers)


def _layer_from_parts(
    parts: list[str] | tuple[str, ...], known_layers: set[str]
) -> str | None:
    if len(parts) < 2 or parts[0] != "aiw":
        return None
    layer = parts[1]
    if layer not in known_layers:
        return None
    return layer
