"""Spec-phase CLI command implementations."""

from __future__ import annotations

from pathlib import Path

from aiw.orchestrator import SpecDraftSession, enter_spec_draft


def prd(root: Path) -> SpecDraftSession:
    """Enter PRD drafting."""
    return enter_spec_draft(root, "aiw prd")


def sdd(root: Path) -> SpecDraftSession:
    """Enter SDD drafting."""
    return enter_spec_draft(root, "aiw sdd")


def adrs(root: Path) -> SpecDraftSession:
    """Enter ADR drafting."""
    return enter_spec_draft(root, "aiw adrs")


def constraints(root: Path) -> SpecDraftSession:
    """Enter constraints drafting."""
    return enter_spec_draft(root, "aiw constraints")
