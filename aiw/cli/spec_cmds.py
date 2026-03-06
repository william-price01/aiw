"""Spec-phase CLI command implementations."""

from __future__ import annotations

from pathlib import Path

from aiw.orchestrator.spec_phase import (
    SpecApprovalResult,
    SpecDraftSession,
    approve_spec_artifact,
    enter_spec_draft,
)


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


def approve_prd(root: Path) -> SpecApprovalResult:
    """Approve the PRD and lock it."""
    return approve_spec_artifact(root, "aiw approve-prd")


def approve_sdd(root: Path) -> SpecApprovalResult:
    """Approve the SDD and lock it."""
    return approve_spec_artifact(root, "aiw approve-sdd")


def approve_adrs(root: Path) -> SpecApprovalResult:
    """Approve ADRs and lock them."""
    return approve_spec_artifact(root, "aiw approve-adrs")


def approve_constraints(root: Path) -> SpecApprovalResult:
    """Approve constraints and lock them."""
    return approve_spec_artifact(root, "aiw approve-constraints")
