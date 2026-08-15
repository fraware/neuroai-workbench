from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import neuroai_workbench.governance_rehearsal as rehearsal
from neuroai_workbench.workspace import Workspace


def test_active_fixture_rejects_missing_or_ambiguous_active_opinion() -> None:
    with pytest.raises(ValueError, match="expected one active opinion for SECURITY, found 0"):
        rehearsal._active_fixture([], track="SECURITY")

    records = [
        {"opinion_id": "GOVOP-a", "review_track": "SECURITY"},
        {"opinion_id": "GOVOP-b", "review_track": "SECURITY"},
    ]
    with pytest.raises(ValueError, match="expected one active opinion for SECURITY, found 2"):
        rehearsal._active_fixture(records, track="SECURITY")


def test_synthetic_authority_probe_fails_closed_if_normalization_ever_accepts_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rehearsal, "_normalize_authority_claim", lambda claim: claim)

    with pytest.raises(AssertionError, match="Synthetic rehearsal authority probe unexpectedly passed"):
        rehearsal._synthetic_authority_probe()


def _patch_rehearsal_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    readiness: dict[str, Any],
    authority_probe: dict[str, Any],
) -> None:
    monkeypatch.setattr(rehearsal, "_record_fixture_opinions", lambda *args, **kwargs: [])
    monkeypatch.setattr(rehearsal, "_record_fixture_dispositions", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        rehearsal,
        "evaluate_governance_completion",
        lambda *args, **kwargs: {"release_readiness": "UNSATISFIED"},
    )
    monkeypatch.setattr(rehearsal, "build_release_readiness_package", lambda *args, **kwargs: readiness)
    monkeypatch.setattr(rehearsal, "_synthetic_authority_probe", lambda: authority_probe)


def test_rehearsal_fails_closed_if_synthetic_inputs_reach_real_authority_readiness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_rehearsal_dependencies(
        monkeypatch,
        readiness={"readiness_state": "READY_FOR_REAL_AUTHORITY_REVIEW"},
        authority_probe={"blocked": True},
    )
    workspace = Workspace.initialize(tmp_path / "workspace")

    with pytest.raises(AssertionError, match="unexpectedly satisfied real-authority readiness"):
        rehearsal.run_synthetic_governance_rehearsal(
            workspace,
            scope_id="GOVSCOPE-test",
            scope_sha256="a" * 64,
            candidate={},
            products=[],
        )


def test_rehearsal_fails_closed_if_authority_boundary_probe_is_unblocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_rehearsal_dependencies(
        monkeypatch,
        readiness={"readiness_state": "NOT_READY"},
        authority_probe={"blocked": False},
    )
    workspace = Workspace.initialize(tmp_path / "workspace")

    with pytest.raises(AssertionError, match="unexpectedly passed the authority boundary"):
        rehearsal.run_synthetic_governance_rehearsal(
            workspace,
            scope_id="GOVSCOPE-test",
            scope_sha256="a" * 64,
            candidate={},
            products=[],
        )
