from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.governance_opinions import REVIEW_TRACKS, record_governance_reviewer_opinion
from neuroai_workbench.governance_release import (
    REAL_AUTHORITY_ACCOUNTABILITY_STATE,
    REAL_GOVERNANCE_EXECUTION_MODE,
    build_release_readiness_package,
    load_governance_release_decisions,
    record_release_authorization,
    record_release_publication,
    verify_governance_release_decisions,
    verify_release_decision_binding,
)
from neuroai_workbench.governance_scope import record_governance_scope_manifest, scope_object_for_path
from neuroai_workbench.successor import generate_from_observatory_release
from neuroai_workbench.util import atomic_write_json, canonical_json_bytes, sha256_bytes
from neuroai_workbench.workspace import Workspace

ROOT = Path(__file__).resolve().parents[2]
SUCCESSOR = ROOT / "examples" / "observatory" / "canonical_successor_snapshot_v1.7.json"
PRODUCTS = [{"product_id": "synthetic-public-projection", "sha256": "a" * 64}]


def _candidate(version: str) -> dict[str, Any]:
    return generate_from_observatory_release(SUCCESSOR, version=version, actor="test-fixture")


def _workspace_and_scope(
    tmp_path: Path,
    candidate: dict[str, Any],
) -> tuple[Workspace, dict[str, Any]]:
    workspace = Workspace.initialize(tmp_path / "workspace")
    public = tmp_path / "public"
    generated = tmp_path / "generated"
    archive = tmp_path / "archive"
    for root in (public, generated, archive):
        root.mkdir()
    fixture_paths = {
        "predecessor": archive / "predecessor.json",
        "candidate": generated / "candidate.json",
        "delta": generated / "delta.json",
        "reopening": generated / "reopening.json",
        "products": generated / "products.json",
        "claims": public / "claims.json",
    }
    for label, path in fixture_paths.items():
        if label == "candidate":
            atomic_write_json(path, candidate)
        else:
            atomic_write_json(path, {"test_fixture_only": label})
    objects = [
        scope_object_for_path(
            role="PREDECESSOR_RELEASE",
            label="Test predecessor",
            object_type="RELEASE",
            path=fixture_paths["predecessor"],
            storage_boundary="ARCHIVE",
            boundary_root=archive,
        ),
        scope_object_for_path(
            role="SUCCESSOR_CANDIDATE",
            label="Test candidate",
            object_type="SUCCESSOR_CANDIDATE",
            path=fixture_paths["candidate"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="DELTA",
            label="Test delta",
            object_type="DELTA",
            path=fixture_paths["delta"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="REOPENING_REGISTER",
            label="Test reopening",
            object_type="REOPENING_REGISTER",
            path=fixture_paths["reopening"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="PRODUCT_MANIFEST",
            label="Test products",
            object_type="PRODUCT_MANIFEST",
            path=fixture_paths["products"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="WITHHELD_CLAIMS",
            label="Test withheld claims",
            object_type="CLAIM_SET",
            path=fixture_paths["claims"],
            storage_boundary="PUBLIC_GIT",
            boundary_root=public,
        ),
    ]
    scope = record_governance_scope_manifest(
        workspace,
        scope_label="TEST FIXTURE ONLY - release governance",
        objects=objects,
        boundary_roots={"PUBLIC_GIT": public, "GENERATED_OUTPUT": generated, "ARCHIVE": archive},
        actor="test-fixture",
    )["manifest"]
    return workspace, scope


def _populate_six_track_support(workspace: Workspace, scope: dict[str, Any]) -> None:
    for track in sorted(REVIEW_TRACKS):
        for suffix in ("a", "b"):
            record_governance_reviewer_opinion(
                workspace,
                scope_id=scope["scope_id"],
                scope_sha256=scope["manifest_sha256"],
                review_track=track,
                opinion_state="SUPPORT",
                reviewer_claim={
                    "reviewer_key": f"test-{track.lower()}-{suffix}",
                    "name_or_role": f"TEST FIXTURE ONLY reviewer {track} {suffix}",
                    "organization": f"TEST FIXTURE ONLY {track} organization {suffix}",
                    "accountability_state": "CLAIMED_HUMAN_REVIEWER",
                    "independence_statement": "TEST FIXTURE ONLY claimed independence; not authenticated.",
                    "conflict_of_interest_disclosure": "NO_CONFLICT_DECLARED: TEST FIXTURE ONLY",
                },
                rationale="TEST FIXTURE ONLY support opinion for release-gate verification.",
                actor="test-fixture",
            )


def _reserved_test_authority_claim() -> dict[str, str]:
    return {
        "name_or_role": "TEST FIXTURE ONLY release authority role",
        "organization": "TEST FIXTURE ONLY organization",
        "authority_basis": "TEST FIXTURE ONLY structural authority-path verification",
        "accountability_state": REAL_AUTHORITY_ACCOUNTABILITY_STATE,
        "execution_mode": REAL_GOVERNANCE_EXECUTION_MODE,
        "authority_evidence_reference": "protected-ref:test-fixture-only/release-authority",
        "authority_evidence_sha256": "b" * 64,
    }


def _ready_fixture(tmp_path: Path) -> tuple[Workspace, dict[str, Any], dict[str, Any]]:
    candidate = _candidate("v1.8-release-fixture")
    workspace, scope = _workspace_and_scope(tmp_path, candidate)
    _populate_six_track_support(workspace, scope)
    return workspace, scope, candidate


def test_complete_six_track_package_is_readiness_only(tmp_path: Path) -> None:
    workspace, scope, candidate = _ready_fixture(tmp_path)
    package = build_release_readiness_package(
        workspace,
        candidate=candidate,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        products=PRODUCTS,
    )

    assert package["readiness_state"] == "READY_FOR_REAL_AUTHORITY_REVIEW"
    assert package["blocker_codes"] == []
    assert package["release_blocking_condition_ids"] == []
    assert package["release_authorization_performed"] is False
    assert package["canonical_successor_authorized"] is False
    assert package["publication_authorized"] is False
    assert package["legacy_gate_classification"] == "NON_AUTHORIZING_CORE_GATE"
    assert len(package["reviewer_opinions"]) == 12
    assert package["owner_dispositions"] == []
    assert package["package_id"].startswith("GOVREADY-")
    assert (
        package["candidate_reference"]["candidate_artifact_sha256"]
        == package["candidate_reference"]["scope_artifact_sha256"]
    )


def test_different_valid_candidate_cannot_reuse_governance_scope(tmp_path: Path) -> None:
    workspace, scope, _ = _ready_fixture(tmp_path)
    substituted = _candidate("v1.8-substituted-candidate")
    package = build_release_readiness_package(
        workspace,
        candidate=substituted,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        products=PRODUCTS,
    )
    assert package["readiness_state"] == "NOT_READY"
    assert "SCOPE_CANDIDATE_ARTIFACT_MISMATCH" in package["blocker_codes"]
    assert (
        package["candidate_reference"]["candidate_artifact_sha256"]
        != package["candidate_reference"]["scope_artifact_sha256"]
    )


def test_local_and_synthetic_authority_claims_fail_closed(tmp_path: Path) -> None:
    workspace, scope, candidate = _ready_fixture(tmp_path)
    local = {
        "name_or_role": "local-user",
        "organization": "local",
        "authority_basis": "local checklist",
        "accountability_state": "CLAIMED_LOCAL_IDENTITY_ONLY",
        "execution_mode": "LOCAL_WORKFLOW",
        "authority_evidence_reference": "protected-ref:test/local",
        "authority_evidence_sha256": "b" * 64,
    }
    with pytest.raises(ValueError, match="reserved CLAIMED_EXTERNAL_RELEASE_AUTHORITY"):
        record_release_authorization(
            workspace,
            candidate=candidate,
            scope_id=scope["scope_id"],
            scope_sha256=scope["manifest_sha256"],
            products=PRODUCTS,
            authority_claim=local,
        )

    synthetic = _reserved_test_authority_claim()
    synthetic["execution_mode"] = "SYNTHETIC_REHEARSAL"
    with pytest.raises(ValueError, match="Synthetic or local execution"):
        record_release_authorization(
            workspace,
            candidate=candidate,
            scope_id=scope["scope_id"],
            scope_sha256=scope["manifest_sha256"],
            products=PRODUCTS,
            authority_claim=synthetic,
        )
    assert load_governance_release_decisions(workspace) == []


def test_reserved_structural_fixture_can_exercise_authorization_path_without_authentication(tmp_path: Path) -> None:
    workspace, scope, candidate = _ready_fixture(tmp_path)
    result = record_release_authorization(
        workspace,
        candidate=candidate,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        products=PRODUCTS,
        authority_claim=_reserved_test_authority_claim(),
        actor="test-fixture",
    )
    decision = result["decision"]
    assert decision["decision_type"] == "AUTHORIZATION"
    assert decision["decision_state"] == "AUTHORIZED"
    assert decision["external_authority_authenticated"] is False
    assert decision["automatic_publication_performed"] is False
    assert decision["release_authority_claim"]["name_or_role"].startswith("TEST FIXTURE ONLY")
    assert (
        decision["candidate_reference"]["candidate_artifact_sha256"]
        == decision["candidate_reference"]["scope_artifact_sha256"]
    )
    assert verify_governance_release_decisions(workspace)["valid"] is True


def test_publication_requires_exact_prior_authorization_and_explicit_evidence(tmp_path: Path) -> None:
    workspace, scope, candidate = _ready_fixture(tmp_path)
    authorization = record_release_authorization(
        workspace,
        candidate=candidate,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        products=PRODUCTS,
        authority_claim=_reserved_test_authority_claim(),
        actor="test-fixture",
    )["decision"]

    with pytest.raises(ValueError, match="one exact prior authorization"):
        record_release_publication(
            workspace,
            candidate=candidate,
            scope_id=scope["scope_id"],
            scope_sha256=scope["manifest_sha256"],
            products=PRODUCTS,
            authorization_decision_id="GOVREL-AUTH-MISSING",
            authority_claim=_reserved_test_authority_claim(),
            publication_evidence={"reference": "public-ref:test-fixture/publication", "sha256": "c" * 64},
        )

    publication = record_release_publication(
        workspace,
        candidate=candidate,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        products=PRODUCTS,
        authorization_decision_id=authorization["decision_id"],
        authority_claim=_reserved_test_authority_claim(),
        publication_evidence={"reference": "public-ref:test-fixture/publication", "sha256": "c" * 64},
        actor="test-fixture",
    )["decision"]
    assert publication["decision_state"] == "PUBLISHED"
    assert publication["prior_authorization_reference"]["decision_id"] == authorization["decision_id"]
    assert publication["publication_evidence"]["sha256"] == "c" * 64
    assert publication["automatic_publication_performed"] is False
    report = verify_governance_release_decisions(workspace)
    assert report["valid"] is True
    assert report["counts"] == {"decisions": 2, "authorizations": 1, "publications": 1}


def test_binding_verifier_detects_product_and_governance_drift(tmp_path: Path) -> None:
    workspace, scope, candidate = _ready_fixture(tmp_path)
    authorization = record_release_authorization(
        workspace,
        candidate=candidate,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        products=PRODUCTS,
        authority_claim=_reserved_test_authority_claim(),
        actor="test-fixture",
    )["decision"]
    exact = verify_release_decision_binding(
        workspace,
        decision_id=authorization["decision_id"],
        candidate=candidate,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        products=PRODUCTS,
    )
    assert exact["valid"] is True

    product_drift = verify_release_decision_binding(
        workspace,
        decision_id=authorization["decision_id"],
        candidate=candidate,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        products=[{"product_id": "synthetic-public-projection", "sha256": "d" * 64}],
    )
    assert product_drift["valid"] is False
    assert any("products binding drift" in error for error in product_drift["errors"])

    record_governance_reviewer_opinion(
        workspace,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        review_track="SECURITY",
        opinion_state="ABSTAIN",
        reviewer_claim={
            "reviewer_key": "test-security-late-abstention",
            "name_or_role": "TEST FIXTURE ONLY late reviewer",
            "organization": "TEST FIXTURE ONLY late organization",
            "accountability_state": "CLAIMED_HUMAN_REVIEWER",
            "independence_statement": "TEST FIXTURE ONLY",
            "conflict_of_interest_disclosure": "NO_CONFLICT_DECLARED: TEST FIXTURE ONLY",
        },
        rationale="TEST FIXTURE ONLY governance drift.",
        actor="test-fixture",
    )
    governance_drift = verify_release_decision_binding(
        workspace,
        decision_id=authorization["decision_id"],
        candidate=candidate,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        products=PRODUCTS,
    )
    assert governance_drift["valid"] is False
    assert any("policy_evaluation_reference binding drift" in error for error in governance_drift["errors"])


def test_legacy_authorized_candidate_is_not_ready_for_new_authority_path(tmp_path: Path) -> None:
    workspace, scope, candidate = _ready_fixture(tmp_path)
    candidate["release_gate"]["current_gate"] = "AUTHORIZED"
    candidate["metadata"]["status"] = "AUTHORIZED"
    candidate["release_gate"]["history"] = [{"target_gate": "AUTHORIZED"}]
    candidate["metadata"].pop("canonical_sha256", None)
    candidate["metadata"]["canonical_sha256"] = sha256_bytes(canonical_json_bytes(candidate))
    package = build_release_readiness_package(
        workspace,
        candidate=candidate,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        products=PRODUCTS,
    )
    assert package["readiness_state"] == "NOT_READY"
    assert package["legacy_gate_classification"] == "LEGACY_LOCAL_AUTHORITY_CLAIM_NOT_GOVERNANCE_COMPLETE"
    assert "LEGACY_LOCAL_AUTHORITY_GATE_PRESENT" in package["blocker_codes"]


def test_malformed_products_and_publication_evidence_fail_closed(tmp_path: Path) -> None:
    workspace, scope, candidate = _ready_fixture(tmp_path)
    with pytest.raises(ValueError, match="At least one release product"):
        build_release_readiness_package(
            workspace,
            candidate=candidate,
            scope_id=scope["scope_id"],
            scope_sha256=scope["manifest_sha256"],
            products=[],
        )
    with pytest.raises(ValueError, match="Duplicate product_id"):
        build_release_readiness_package(
            workspace,
            candidate=candidate,
            scope_id=scope["scope_id"],
            scope_sha256=scope["manifest_sha256"],
            products=PRODUCTS + PRODUCTS,
        )
    authorization = record_release_authorization(
        workspace,
        candidate=candidate,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        products=PRODUCTS,
        authority_claim=_reserved_test_authority_claim(),
        actor="test-fixture",
    )["decision"]
    with pytest.raises(ValueError, match="public-ref: or protected-ref:"):
        record_release_publication(
            workspace,
            candidate=candidate,
            scope_id=scope["scope_id"],
            scope_sha256=scope["manifest_sha256"],
            products=PRODUCTS,
            authorization_decision_id=authorization["decision_id"],
            authority_claim=_reserved_test_authority_claim(),
            publication_evidence={"reference": "https://example.invalid", "sha256": "c" * 64},
        )


def test_decision_store_detects_record_tampering(tmp_path: Path) -> None:
    workspace, scope, candidate = _ready_fixture(tmp_path)
    result = record_release_authorization(
        workspace,
        candidate=candidate,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        products=PRODUCTS,
        authority_claim=_reserved_test_authority_claim(),
        actor="test-fixture",
    )
    decision = result["decision"]
    path = Path(result["path"])
    tampered = {**decision, "recorded_by": "tampered"}
    atomic_write_json(path, tampered)
    report = verify_governance_release_decisions(workspace)
    assert report["valid"] is False
    assert any("hash mismatch" in error for error in report["errors"])


def test_duplicate_authorization_is_rejected(tmp_path: Path) -> None:
    workspace, scope, candidate = _ready_fixture(tmp_path)
    kwargs = {
        "candidate": candidate,
        "scope_id": scope["scope_id"],
        "scope_sha256": scope["manifest_sha256"],
        "products": PRODUCTS,
        "authority_claim": _reserved_test_authority_claim(),
        "actor": "test-fixture",
    }
    record_release_authorization(workspace, **kwargs)
    with pytest.raises(ValueError, match="already has an authorization decision"):
        record_release_authorization(workspace, **kwargs)
