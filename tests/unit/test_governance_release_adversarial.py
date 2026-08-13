from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

import neuroai_workbench.governance_release as release_mod
from neuroai_workbench.governance_release import (
    REAL_AUTHORITY_ACCOUNTABILITY_STATE,
    REAL_GOVERNANCE_EXECUTION_MODE,
    RELEASE_DECISION_BOUNDARY,
    _assert_digest,
    _candidate_artifact_sha256,
    _condition_metrics if False else _candidate_artifact_sha256,
)
from neuroai_workbench.util import atomic_write_json
from neuroai_workbench.workspace import Workspace


D64_A = "a" * 64
D64_B = "b" * 64
D64_C = "c" * 64
D64_D = "d" * 64


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace.initialize(tmp_path / "workspace")


def _candidate() -> dict[str, Any]:
    return {
        "metadata": {
            "candidate_id": "SC-TEST-FIXTURE",
            "canonical_sha256": D64_A,
        },
        "predecessor_reference": {
            "release_version": "v-test",
            "sha256": D64_B,
        },
        "release_gate": {"current_gate": "CANDIDATE", "history": []},
        "withheld_claims": ["TEST FIXTURE ONLY withheld claim"],
    }


def _evaluation(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "integrity_valid": True,
        "release_readiness": "SATISFIED",
        "evaluation_id": "GOVEVAL-TEST",
        "evaluation_sha256": D64_A,
        "input_binding_sha256": D64_B,
        "policy_id": "GOVPOLICY-TEST",
        "policy_version": "1.0.0",
        "policy_sha256": D64_C,
        "input_binding": {
            "opinion_records": [],
            "owner_disposition_records": [],
        },
        "track_results": {},
    }
    value.update(overrides)
    return value


def _ready_package() -> dict[str, Any]:
    return {
        "readiness_state": "READY_FOR_REAL_AUTHORITY_REVIEW",
        "blocker_codes": [],
        "release_blocking_condition_ids": [],
        "candidate_reference": {
            "candidate_id": "SC-TEST-FIXTURE",
            "candidate_sha256": D64_A,
            "candidate_artifact_sha256": D64_B,
            "scope_artifact_sha256": D64_B,
        },
        "predecessor_reference": {"release_version": "v-test", "sha256": D64_C},
        "governance_scope_reference": {"scope_id": "GOVSCOPE-TEST", "scope_sha256": D64_D},
        "reviewer_opinions": [],
        "owner_dispositions": [],
        "policy_evaluation_reference": {
            "evaluation_id": "GOVEVAL-TEST",
            "evaluation_sha256": D64_A,
            "input_binding_sha256": D64_B,
            "policy_id": "GOVPOLICY-TEST",
            "policy_version": "1.0.0",
            "policy_sha256": D64_C,
        },
        "products": [{"product_id": "TEST-FIXTURE-PRODUCT", "sha256": D64_D}],
        "withheld_claims_sha256": D64_A,
        "package_id": "GOVREADY-TEST",
        "package_sha256": D64_B,
    }


def _authority_claim() -> dict[str, str]:
    return {
        "name_or_role": "TEST FIXTURE ONLY release role",
        "organization": "TEST FIXTURE ONLY organization",
        "authority_basis": "TEST FIXTURE ONLY structural path",
        "accountability_state": REAL_AUTHORITY_ACCOUNTABILITY_STATE,
        "execution_mode": REAL_GOVERNANCE_EXECUTION_MODE,
        "authority_evidence_reference": "protected-ref:test-fixture-only/authority",
        "authority_evidence_sha256": D64_C,
    }


def _authorization_record() -> dict[str, Any]:
    record = release_mod._decision_core(
        decision_id="GOVREL-AUTH-TEST0001",
        decision_type="AUTHORIZATION",
        package=_ready_package(),
        authority_claim=_authority_claim(),
        actor="test-fixture",
    )
    record["decision_sha256"] = release_mod._decision_hash(record)
    return record


def _publication_record(authorization: dict[str, Any]) -> dict[str, Any]:
    record = release_mod._decision_core(
        decision_id="GOVREL-PUB-TEST0001",
        decision_type="PUBLICATION",
        package=_ready_package(),
        authority_claim=_authority_claim(),
        actor="test-fixture",
    )
    record["prior_authorization_reference"] = {
        "decision_id": authorization["decision_id"],
        "decision_sha256": authorization["decision_sha256"],
    }
    record["publication_evidence"] = {
        "reference": "public-ref:test-fixture-only/publication",
        "sha256": D64_D,
    }
    record["decision_sha256"] = release_mod._decision_hash(record)
    return record


def _valid_chain() -> dict[str, Any]:
    return {"valid": True, "trailer_valid": True, "errors": [], "trailer_errors": []}


def test_digest_validation_rejects_type_length_and_charset() -> None:
    assert _assert_digest(D64_A, "digest") == D64_A
    for value in (None, "a" * 63, "A" * 64, "g" * 64):
        with pytest.raises(ValueError, match="64-character lowercase hexadecimal"):
            _assert_digest(value, "digest")


def test_release_decision_loader_rejects_non_object(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    root = workspace.root / "governance" / "release-decisions"
    root.mkdir(parents=True)
    atomic_write_json(root / "invalid.json", ["not", "an", "object"])
    with pytest.raises(ValueError, match="must be an object"):
        release_mod.load_governance_release_decisions(workspace)


def test_product_normalization_fail_closed_edges() -> None:
    with pytest.raises(ValueError, match="At least one"):
        release_mod._normalize_products([])
    with pytest.raises(ValueError, match="must be an object"):
        release_mod._normalize_products(["invalid"])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="product_id is required"):
        release_mod._normalize_products([{"product_id": "", "sha256": D64_A}])
    with pytest.raises(ValueError, match="Duplicate product_id"):
        release_mod._normalize_products(
            [
                {"product_id": "p", "sha256": D64_A},
                {"product_id": "p", "sha256": D64_B},
            ]
        )
    with pytest.raises(ValueError, match="SHA-256 digest"):
        release_mod._normalize_products([{"product_id": "p", "sha256": "bad"}])
    assert release_mod._normalize_products(
        [
            {"product_id": "z", "sha256": D64_A},
            {"product_id": "a", "sha256": D64_B},
        ]
    )[0]["product_id"] == "a"


def test_legacy_gate_classifier_covers_malformed_history_and_authorizing_history() -> None:
    assert release_mod._legacy_gate_classification({"release_gate": "invalid"}) == "INVALID_GATE_STATE"
    assert (
        release_mod._legacy_gate_classification(
            {"release_gate": {"current_gate": "CANDIDATE", "history": "invalid"}}
        )
        == "NON_AUTHORIZING_CORE_GATE"
    )
    assert (
        release_mod._legacy_gate_classification(
            {"release_gate": {"current_gate": "AUTHORIZED", "history": []}}
        )
        == "LEGACY_LOCAL_AUTHORITY_CLAIM_NOT_GOVERNANCE_COMPLETE"
    )
    assert (
        release_mod._legacy_gate_classification(
            {
                "release_gate": {
                    "current_gate": "REVIEWED",
                    "history": [None, {"target_gate": "PUBLISHED"}],
                }
            }
        )
        == "LEGACY_LOCAL_AUTHORITY_CLAIM_NOT_GOVERNANCE_COMPLETE"
    )


def test_scope_candidate_digest_helper_fails_closed_on_ambiguity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    kwargs = {"scope_id": "scope", "scope_sha256": D64_A}

    monkeypatch.setattr(release_mod, "load_governance_scope_manifests", lambda _: [])
    assert release_mod._scope_candidate_artifact_sha256(workspace, **kwargs) is None

    manifest = {"scope_id": "scope", "manifest_sha256": D64_A, "objects": "invalid"}
    monkeypatch.setattr(release_mod, "load_governance_scope_manifests", lambda _: [manifest])
    assert release_mod._scope_candidate_artifact_sha256(workspace, **kwargs) is None

    manifest["objects"] = [{"role": "OTHER", "sha256": D64_B}]
    assert release_mod._scope_candidate_artifact_sha256(workspace, **kwargs) is None

    manifest["objects"] = [
        {"role": "SUCCESSOR_CANDIDATE", "sha256": D64_B},
        {"role": "SUCCESSOR_CANDIDATE", "sha256": D64_C},
    ]
    assert release_mod._scope_candidate_artifact_sha256(workspace, **kwargs) is None

    manifest["objects"] = [{"role": "SUCCESSOR_CANDIDATE", "sha256": "bad"}]
    assert release_mod._scope_candidate_artifact_sha256(workspace, **kwargs) is None

    manifest["objects"] = [{"role": "SUCCESSOR_CANDIDATE", "sha256": D64_B}]
    assert release_mod._scope_candidate_artifact_sha256(workspace, **kwargs) == D64_B

    monkeypatch.setattr(release_mod, "load_governance_scope_manifests", lambda _: [manifest, deepcopy(manifest)])
    assert release_mod._scope_candidate_artifact_sha256(workspace, **kwargs) is None


def test_evaluation_reference_extraction_ignores_malformed_entries() -> None:
    assert release_mod._evaluation_refs({}) == ([], [])
    opinions, dispositions = release_mod._evaluation_refs(
        {
            "input_binding": {
                "opinion_records": [None, {"opinion_id": "op", "opinion_sha256": D64_A}],
                "owner_disposition_records": [
                    "bad",
                    {
                        "disposition_id": "disp",
                        "disposition_sha256": D64_B,
                        "condition_register_sha256": D64_C,
                    },
                ],
            }
        }
    )
    assert opinions == [{"opinion_id": "op", "opinion_sha256": D64_A}]
    assert dispositions == [
        {
            "disposition_id": "disp",
            "disposition_sha256": D64_B,
            "condition_register_sha256": D64_C,
        }
    ]


def _patch_readiness_inputs(
    monkeypatch: pytest.MonkeyPatch,
    candidate: dict[str, Any],
    evaluation: dict[str, Any] | None = None,
    *,
    scope_digest: str | None = None,
) -> None:
    monkeypatch.setattr(release_mod, "validate_successor_candidate", lambda _: {"valid": True})
    expected = _candidate_artifact_sha256(candidate) if scope_digest is None else scope_digest
    monkeypatch.setattr(release_mod, "_scope_candidate_artifact_sha256", lambda *args, **kwargs: expected)
    selected = _evaluation() if evaluation is None else evaluation
    monkeypatch.setattr(release_mod, "evaluate_governance_completion", lambda *args, **kwargs: selected)


def test_readiness_builder_rejects_invalid_candidate_and_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    monkeypatch.setattr(release_mod, "validate_successor_candidate", lambda _: {"valid": False})
    with pytest.raises(ValueError, match="failed validation"):
        release_mod.build_release_readiness_package(
            workspace,
            candidate=_candidate(),
            scope_id="scope",
            scope_sha256=D64_A,
            products=[{"product_id": "p", "sha256": D64_A}],
        )

    candidate = _candidate()
    _patch_readiness_inputs(monkeypatch, candidate)
    malformed = deepcopy(candidate)
    malformed["metadata"] = None
    with pytest.raises(ValueError, match="metadata and predecessor"):
        release_mod.build_release_readiness_package(
            workspace,
            candidate=malformed,
            scope_id="scope",
            scope_sha256=D64_A,
            products=[{"product_id": "p", "sha256": D64_A}],
        )

    malformed = deepcopy(candidate)
    malformed["predecessor_reference"] = None
    with pytest.raises(ValueError, match="metadata and predecessor"):
        release_mod.build_release_readiness_package(
            workspace,
            candidate=malformed,
            scope_id="scope",
            scope_sha256=D64_A,
            products=[{"product_id": "p", "sha256": D64_A}],
        )


def test_readiness_builder_rejects_invalid_hashes_and_withheld_claims(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    candidate = _candidate()
    _patch_readiness_inputs(monkeypatch, candidate)

    malformed = deepcopy(candidate)
    malformed["metadata"]["canonical_sha256"] = "bad"
    with pytest.raises(ValueError, match="canonical_sha256"):
        release_mod.build_release_readiness_package(
            workspace,
            candidate=malformed,
            scope_id="scope",
            scope_sha256=D64_A,
            products=[{"product_id": "p", "sha256": D64_A}],
        )

    malformed = deepcopy(candidate)
    malformed["predecessor_reference"]["sha256"] = "bad"
    with pytest.raises(ValueError, match="predecessor_reference.sha256"):
        release_mod.build_release_readiness_package(
            workspace,
            candidate=malformed,
            scope_id="scope",
            scope_sha256=D64_A,
            products=[{"product_id": "p", "sha256": D64_A}],
        )

    with pytest.raises(ValueError, match="scope_sha256"):
        release_mod.build_release_readiness_package(
            workspace,
            candidate=candidate,
            scope_id="scope",
            scope_sha256="bad",
            products=[{"product_id": "p", "sha256": D64_A}],
        )

    malformed = deepcopy(candidate)
    malformed["withheld_claims"] = []
    with pytest.raises(ValueError, match="withheld claims"):
        release_mod.build_release_readiness_package(
            workspace,
            candidate=malformed,
            scope_id="scope",
            scope_sha256=D64_A,
            products=[{"product_id": "p", "sha256": D64_A}],
        )


def test_readiness_builder_exposes_all_blocker_classes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    candidate = _candidate()
    evaluation = _evaluation(
        integrity_valid=False,
        release_readiness="UNSATISFIED",
        track_results={"SECURITY": {"release_blocking_condition_ids": ["COND-1"]}, "DOMAIN": "invalid"},
    )
    _patch_readiness_inputs(monkeypatch, candidate, evaluation, scope_digest=D64_D)
    package = release_mod.build_release_readiness_package(
        workspace,
        candidate=candidate,
        scope_id="scope",
        scope_sha256=D64_A,
        products=[{"product_id": "p", "sha256": D64_A}],
    )
    assert package["readiness_state"] == "NOT_READY"
    assert set(package["blocker_codes"]) == {
        "SCOPE_CANDIDATE_ARTIFACT_MISMATCH",
        "GOVERNANCE_INPUT_INTEGRITY_INVALID",
        "GOVERNANCE_POLICY_UNSATISFIED",
        "UNRESOLVED_RELEASE_BLOCKING_CONDITIONS",
    }
    assert package["release_blocking_condition_ids"] == ["COND-1"]

    _patch_readiness_inputs(monkeypatch, candidate, _evaluation(), scope_digest=None)
    monkeypatch.setattr(release_mod, "_scope_candidate_artifact_sha256", lambda *args, **kwargs: None)
    package = release_mod.build_release_readiness_package(
        workspace,
        candidate=candidate,
        scope_id="scope",
        scope_sha256=D64_A,
        products=[{"product_id": "p", "sha256": D64_A}],
    )
    assert "SCOPE_CANDIDATE_ARTIFACT_MISSING" in package["blocker_codes"]


def test_authority_claim_normalization_rejects_every_bypass_axis() -> None:
    claim = _authority_claim()
    for field in ("name_or_role", "organization", "authority_basis"):
        malformed = deepcopy(claim)
        malformed[field] = ""
        with pytest.raises(ValueError, match=field):
            release_mod._normalize_authority_claim(malformed)

    malformed = deepcopy(claim)
    malformed["accountability_state"] = "CLAIMED_LOCAL_IDENTITY_ONLY"
    with pytest.raises(ValueError, match="reserved CLAIMED_EXTERNAL"):
        release_mod._normalize_authority_claim(malformed)

    malformed = deepcopy(claim)
    malformed["execution_mode"] = "SYNTHETIC_REHEARSAL"
    with pytest.raises(ValueError, match="Synthetic or local execution"):
        release_mod._normalize_authority_claim(malformed)

    for reference in ("public-ref:authority", "protected-ref:"):
        malformed = deepcopy(claim)
        malformed["authority_evidence_reference"] = reference
        with pytest.raises(ValueError, match="protected-ref"):
            release_mod._normalize_authority_claim(malformed)

    malformed = deepcopy(claim)
    malformed["authority_evidence_sha256"] = "bad"
    with pytest.raises(ValueError, match="authority_evidence_sha256"):
        release_mod._normalize_authority_claim(malformed)

    normalized = release_mod._normalize_authority_claim(claim)
    assert normalized["execution_mode"] == REAL_GOVERNANCE_EXECUTION_MODE


def test_publication_evidence_and_package_reference_fail_closed() -> None:
    for reference in ("https://example.invalid", "public-ref:", "protected-ref:"):
        with pytest.raises(ValueError):
            release_mod._normalize_publication_evidence({"reference": reference, "sha256": D64_A})
    with pytest.raises(ValueError, match="publication_evidence.sha256"):
        release_mod._normalize_publication_evidence(
            {"reference": "public-ref:test", "sha256": "bad"}
        )
    assert release_mod._normalize_publication_evidence(
        {"reference": "protected-ref:test", "sha256": D64_A}
    )["sha256"] == D64_A
    with pytest.raises(ValueError, match="readiness_package.package_sha256"):
        release_mod._package_reference({"package_id": "x", "package_sha256": "bad"})


def test_readiness_guard_distinguishes_each_failure_axis() -> None:
    with pytest.raises(ValueError, match="not ready"):
        release_mod._ensure_ready({"readiness_state": "NOT_READY"})
    with pytest.raises(ValueError, match="contains blockers"):
        release_mod._ensure_ready(
            {
                "readiness_state": "READY_FOR_REAL_AUTHORITY_REVIEW",
                "blocker_codes": ["B"],
            }
        )
    with pytest.raises(ValueError, match="release-blocking"):
        release_mod._ensure_ready(
            {
                "readiness_state": "READY_FOR_REAL_AUTHORITY_REVIEW",
                "blocker_codes": [],
                "release_blocking_condition_ids": ["COND"],
            }
        )
    release_mod._ensure_ready(
        {
            "readiness_state": "READY_FOR_REAL_AUTHORITY_REVIEW",
            "blocker_codes": [],
            "release_blocking_condition_ids": [],
        }
    )


def _patch_recording_prerequisites(
    monkeypatch: pytest.MonkeyPatch,
    *,
    records: list[dict[str, Any]] | None = None,
    store_valid: bool = True,
) -> None:
    monkeypatch.setattr(release_mod, "build_release_readiness_package", lambda *args, **kwargs: _ready_package())
    monkeypatch.setattr(
        release_mod,
        "verify_governance_release_decisions",
        lambda _: {"valid": store_valid, "errors": []},
    )
    monkeypatch.setattr(release_mod, "load_governance_release_decisions", lambda _: list(records or []))


def test_authorization_rejects_invalid_store_and_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    _patch_recording_prerequisites(monkeypatch, store_valid=False)
    with pytest.raises(ValueError, match="store is invalid"):
        release_mod.record_release_authorization(
            workspace,
            candidate=_candidate(),
            scope_id="scope",
            scope_sha256=D64_A,
            products=[{"product_id": "p", "sha256": D64_A}],
            authority_claim=_authority_claim(),
        )

    _patch_recording_prerequisites(monkeypatch)
    monkeypatch.setattr(release_mod, "_schema_errors", lambda _: ["TEST schema error"])
    with pytest.raises(ValueError, match="schema validation"):
        release_mod.record_release_authorization(
            workspace,
            candidate=_candidate(),
            scope_id="scope",
            scope_sha256=D64_A,
            products=[{"product_id": "p", "sha256": D64_A}],
            authority_claim=_authority_claim(),
        )


def test_publication_rejects_invalid_store_wrong_prior_and_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    auth = _authorization_record()

    _patch_recording_prerequisites(monkeypatch, store_valid=False)
    with pytest.raises(ValueError, match="store is invalid"):
        release_mod.record_release_publication(
            workspace,
            candidate=_candidate(),
            scope_id="scope",
            scope_sha256=D64_A,
            products=[{"product_id": "p", "sha256": D64_A}],
            authorization_decision_id=auth["decision_id"],
            authority_claim=_authority_claim(),
            publication_evidence={"reference": "public-ref:test", "sha256": D64_A},
        )

    wrong_type = deepcopy(auth)
    wrong_type["decision_type"] = "PUBLICATION"
    wrong_type["decision_state"] = "PUBLISHED"
    _patch_recording_prerequisites(monkeypatch, records=[wrong_type])
    with pytest.raises(ValueError, match="not an AUTHORIZED"):
        release_mod.record_release_publication(
            workspace,
            candidate=_candidate(),
            scope_id="scope",
            scope_sha256=D64_A,
            products=[{"product_id": "p", "sha256": D64_A}],
            authorization_decision_id=wrong_type["decision_id"],
            authority_claim=_authority_claim(),
            publication_evidence={"reference": "public-ref:test", "sha256": D64_A},
        )

    stale = deepcopy(auth)
    stale["readiness_package_reference"] = {"package_id": "other", "package_sha256": D64_D}
    _patch_recording_prerequisites(monkeypatch, records=[stale])
    with pytest.raises(ValueError, match="readiness package differs"):
        release_mod.record_release_publication(
            workspace,
            candidate=_candidate(),
            scope_id="scope",
            scope_sha256=D64_A,
            products=[{"product_id": "p", "sha256": D64_A}],
            authorization_decision_id=stale["decision_id"],
            authority_claim=_authority_claim(),
            publication_evidence={"reference": "public-ref:test", "sha256": D64_A},
        )

    wrong_candidate = deepcopy(auth)
    wrong_candidate["candidate_reference"] = deepcopy(auth["candidate_reference"])
    wrong_candidate["candidate_reference"]["candidate_id"] = "SC-OTHER"
    _patch_recording_prerequisites(monkeypatch, records=[wrong_candidate])
    with pytest.raises(ValueError, match="candidate differs"):
        release_mod.record_release_publication(
            workspace,
            candidate=_candidate(),
            scope_id="scope",
            scope_sha256=D64_A,
            products=[{"product_id": "p", "sha256": D64_A}],
            authorization_decision_id=wrong_candidate["decision_id"],
            authority_claim=_authority_claim(),
            publication_evidence={"reference": "public-ref:test", "sha256": D64_A},
        )


def test_publication_rejects_duplicate_and_schema_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    auth = _authorization_record()
    publication = _publication_record(auth)
    _patch_recording_prerequisites(monkeypatch, records=[auth, publication])
    with pytest.raises(ValueError, match="already has a publication"):
        release_mod.record_release_publication(
            workspace,
            candidate=_candidate(),
            scope_id="scope",
            scope_sha256=D64_A,
            products=[{"product_id": "p", "sha256": D64_A}],
            authorization_decision_id=auth["decision_id"],
            authority_claim=_authority_claim(),
            publication_evidence={"reference": "public-ref:test", "sha256": D64_A},
        )

    _patch_recording_prerequisites(monkeypatch, records=[auth])
    monkeypatch.setattr(release_mod, "_schema_errors", lambda _: ["TEST schema error"])
    with pytest.raises(ValueError, match="schema validation"):
        release_mod.record_release_publication(
            workspace,
            candidate=_candidate(),
            scope_id="scope",
            scope_sha256=D64_A,
            products=[{"product_id": "p", "sha256": D64_A}],
            authorization_decision_id=auth["decision_id"],
            authority_claim=_authority_claim(),
            publication_evidence={"reference": "public-ref:test", "sha256": D64_A},
        )


def _event_for(record: dict[str, Any]) -> dict[str, Any]:
    action = (
        "GOVERNANCE_RELEASE_AUTHORIZATION_RECORDED"
        if record["decision_type"] == "AUTHORIZATION"
        else "GOVERNANCE_RELEASE_PUBLICATION_RECORDED"
    )
    return {"action": action, "payload": release_mod._event_payload(record)}


def test_store_verifier_detects_record_level_corruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    record = _authorization_record()
    record["_unsupported"] = True
    record["decision_sha256"] = D64_D
    record["boundary"] = "wrong"
    record["external_authority_authenticated"] = True
    record["automatic_publication_performed"] = True
    record["candidate_reference"] = deepcopy(record["candidate_reference"])
    record["candidate_reference"]["scope_artifact_sha256"] = D64_D

    monkeypatch.setattr(release_mod, "load_governance_release_decisions", lambda _: [record])
    monkeypatch.setattr(release_mod, "load_events", lambda _: [])
    monkeypatch.setattr(release_mod, "verify_chain", lambda _: _valid_chain())
    report = release_mod.verify_governance_release_decisions(workspace)
    joined = "\n".join(report["errors"])
    assert report["valid"] is False
    assert "unsupported private fields" in joined
    assert "hash mismatch" in joined
    assert "schema invalid" in joined
    assert "authority boundary mismatch" in joined
    assert "external authority authentication" in joined
    assert "automatic publication" in joined
    assert "candidate artifact differs" in joined
    assert "matching append-only event is missing" in joined


def test_store_verifier_detects_duplicate_event_and_duplicate_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    record = _authorization_record()
    duplicate = deepcopy(record)
    monkeypatch.setattr(release_mod, "load_governance_release_decisions", lambda _: [record, duplicate])
    event = _event_for(record)
    monkeypatch.setattr(release_mod, "load_events", lambda _: [event, deepcopy(event)])
    monkeypatch.setattr(release_mod, "verify_chain", lambda _: _valid_chain())
    report = release_mod.verify_governance_release_decisions(workspace)
    joined = "\n".join(report["errors"])
    assert "duplicate decision_id" in joined
    assert "multiple matching append-only events" in joined
    assert "authorization decisions recorded" in joined


def test_store_verifier_handles_event_load_and_chain_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    record = _authorization_record()
    monkeypatch.setattr(release_mod, "load_governance_release_decisions", lambda _: [record])

    def fail_events(_: Path) -> list[dict[str, Any]]:
        raise ValueError("TEST event load failure")

    monkeypatch.setattr(release_mod, "load_events", fail_events)
    monkeypatch.setattr(
        release_mod,
        "verify_chain",
        lambda _: {
            "valid": False,
            "trailer_valid": False,
            "errors": ["TEST chain failure"],
            "trailer_errors": ["TEST trailer failure"],
        },
    )
    report = release_mod.verify_governance_release_decisions(workspace)
    joined = "\n".join(report["errors"])
    assert "event log load failed" in joined
    assert "event chain: TEST chain failure" in joined
    assert "event chain trailer: TEST trailer failure" in joined


def test_store_verifier_rejects_publication_without_or_with_unknown_prior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    auth = _authorization_record()
    publication = _publication_record(auth)
    publication.pop("prior_authorization_reference")
    publication["decision_sha256"] = release_mod._decision_hash(publication)
    monkeypatch.setattr(release_mod, "load_governance_release_decisions", lambda _: [publication])
    monkeypatch.setattr(release_mod, "load_events", lambda _: [_event_for(publication)])
    monkeypatch.setattr(release_mod, "verify_chain", lambda _: _valid_chain())
    report = release_mod.verify_governance_release_decisions(workspace)
    assert any("publication lacks prior authorization" in error for error in report["errors"])

    publication = _publication_record(auth)
    publication["prior_authorization_reference"]["decision_id"] = "GOVREL-AUTH-MISSING"
    publication["decision_sha256"] = release_mod._decision_hash(publication)
    monkeypatch.setattr(release_mod, "load_governance_release_decisions", lambda _: [publication])
    monkeypatch.setattr(release_mod, "load_events", lambda _: [_event_for(publication)])
    report = release_mod.verify_governance_release_decisions(workspace)
    assert any("prior authorization GOVREL-AUTH-MISSING is missing" in error for error in report["errors"])


def test_store_verifier_rejects_wrong_prior_hash_candidate_and_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    auth = _authorization_record()
    publication = _publication_record(auth)
    publication["prior_authorization_reference"]["decision_sha256"] = D64_D
    publication["candidate_reference"] = deepcopy(publication["candidate_reference"])
    publication["candidate_reference"]["candidate_id"] = "SC-OTHER"
    publication["readiness_package_reference"] = {
        "package_id": "GOVREADY-OTHER",
        "package_sha256": D64_D,
    }
    publication["decision_sha256"] = release_mod._decision_hash(publication)
    monkeypatch.setattr(release_mod, "load_governance_release_decisions", lambda _: [auth, publication])
    monkeypatch.setattr(
        release_mod,
        "load_events",
        lambda _: [_event_for(auth), _event_for(publication)],
    )
    monkeypatch.setattr(release_mod, "verify_chain", lambda _: _valid_chain())
    report = release_mod.verify_governance_release_decisions(workspace)
    joined = "\n".join(report["errors"])
    assert "prior authorization hash mismatch" in joined
    assert "candidate differs from prior authorization" in joined
    assert "readiness package differs from prior authorization" in joined


def test_store_verifier_rejects_non_authorization_prior_and_duplicate_publications(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    auth = _authorization_record()
    prior_publication = _publication_record(auth)
    publication_a = _publication_record(auth)
    publication_a["decision_id"] = "GOVREL-PUB-TEST0002"
    publication_a["prior_authorization_reference"] = {
        "decision_id": prior_publication["decision_id"],
        "decision_sha256": prior_publication["decision_sha256"],
    }
    publication_a["decision_sha256"] = release_mod._decision_hash(publication_a)
    publication_b = deepcopy(publication_a)
    publication_b["decision_id"] = "GOVREL-PUB-TEST0003"
    publication_b["decision_sha256"] = release_mod._decision_hash(publication_b)

    records = [auth, prior_publication, publication_a, publication_b]
    monkeypatch.setattr(release_mod, "load_governance_release_decisions", lambda _: records)
    monkeypatch.setattr(release_mod, "load_events", lambda _: [_event_for(item) for item in records])
    monkeypatch.setattr(release_mod, "verify_chain", lambda _: _valid_chain())
    report = release_mod.verify_governance_release_decisions(workspace)
    joined = "\n".join(report["errors"])
    assert "is not an authorization" in joined
    assert "publication decisions recorded" in joined


def test_binding_verifier_missing_decision_and_all_field_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    monkeypatch.setattr(
        release_mod,
        "verify_governance_release_decisions",
        lambda _: {"valid": True, "errors": []},
    )
    monkeypatch.setattr(release_mod, "load_governance_release_decisions", lambda _: [])
    missing = release_mod.verify_release_decision_binding(
        workspace,
        decision_id="GOVREL-AUTH-MISSING",
        candidate=_candidate(),
        scope_id="scope",
        scope_sha256=D64_A,
        products=[{"product_id": "p", "sha256": D64_A}],
    )
    assert missing["valid"] is False
    assert any("expected exactly one" in error for error in missing["errors"])

    decision = _authorization_record()
    package = _ready_package()
    package["package_id"] = "GOVREADY-OTHER"
    package["package_sha256"] = D64_D
    package["candidate_reference"] = {"different": True}
    package["predecessor_reference"] = {"different": True}
    package["governance_scope_reference"] = {"different": True}
    package["reviewer_opinions"] = [{"different": True}]
    package["owner_dispositions"] = [{"different": True}]
    package["policy_evaluation_reference"] = {"different": True}
    package["products"] = [{"different": True}]
    package["withheld_claims_sha256"] = D64_D
    monkeypatch.setattr(release_mod, "load_governance_release_decisions", lambda _: [decision])
    monkeypatch.setattr(release_mod, "build_release_readiness_package", lambda *args, **kwargs: package)
    drift = release_mod.verify_release_decision_binding(
        workspace,
        decision_id=decision["decision_id"],
        candidate=_candidate(),
        scope_id="scope",
        scope_sha256=D64_A,
        products=[{"product_id": "p", "sha256": D64_A}],
    )
    assert drift["valid"] is False
    joined = "\n".join(drift["errors"])
    assert "readiness package drift" in joined
    for field in (
        "candidate_reference",
        "predecessor_reference",
        "governance_scope_reference",
        "reviewer_opinions",
        "owner_dispositions",
        "policy_evaluation_reference",
        "products",
        "withheld_claims_sha256",
    ):
        assert f"{field} binding drift" in joined


def test_schema_helper_reports_json_schema_path() -> None:
    errors = release_mod._schema_errors({"schema_version": "0"})
    assert errors


def test_decision_hash_ignores_runtime_path_but_not_controlled_fields() -> None:
    record = _authorization_record()
    original = release_mod._decision_hash(record)
    with_path = {**record, "_path": "/tmp/test-fixture"}
    assert release_mod._decision_hash(with_path) == original
    mutated = {**record, "recorded_by": "other"}
    assert release_mod._decision_hash(mutated) != original


def test_candidate_artifact_hash_is_serialization_sensitive() -> None:
    first = _candidate_artifact_sha256({"x": "é", "y": 1})
    second = _candidate_artifact_sha256({"y": 1, "x": "é"})
    assert first != second
