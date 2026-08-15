from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from neuroai_workbench.governance_dispositions import verify_governance_owner_dispositions
from neuroai_workbench.governance_opinions import REVIEW_TRACKS, verify_governance_reviewer_opinions
from neuroai_workbench.governance_rehearsal import (
    REHEARSAL_EXECUTION_MODE,
    REHEARSAL_RECORD_TYPE,
    TRACK_QUESTIONS,
    build_handoff_template,
    run_synthetic_governance_rehearsal,
)
from neuroai_workbench.governance_release import load_governance_release_decisions
from neuroai_workbench.governance_scope import record_governance_scope_manifest, scope_object_for_path
from neuroai_workbench.successor import generate_from_observatory_release
from neuroai_workbench.util import atomic_write_json
from neuroai_workbench.workspace import Workspace

ROOT = Path(__file__).resolve().parents[2]
SUCCESSOR = ROOT / "examples" / "observatory" / "canonical_successor_snapshot_v1.7.json"
PRODUCTS = [{"product_id": "TEST-FIXTURE-PRODUCT", "sha256": "a" * 64}]


def _fixture(tmp_path: Path) -> tuple[Workspace, dict[str, Any], dict[str, Any]]:
    candidate = generate_from_observatory_release(
        SUCCESSOR,
        version="v1.8-synthetic-rehearsal",
        actor="synthetic-rehearsal",
    )
    workspace = Workspace.initialize(tmp_path / "workspace")
    public = tmp_path / "public"
    generated = tmp_path / "generated"
    archive = tmp_path / "archive"
    for root in (public, generated, archive):
        root.mkdir()
    paths = {
        "predecessor": archive / "predecessor.json",
        "candidate": generated / "candidate.json",
        "delta": generated / "delta.json",
        "reopening": generated / "reopening.json",
        "products": generated / "products.json",
        "claims": public / "claims.json",
    }
    for label, path in paths.items():
        atomic_write_json(path, candidate if label == "candidate" else {"test_fixture_only": label})
    objects = [
        scope_object_for_path(
            role="PREDECESSOR_RELEASE",
            label="TEST FIXTURE predecessor",
            object_type="RELEASE",
            path=paths["predecessor"],
            storage_boundary="ARCHIVE",
            boundary_root=archive,
        ),
        scope_object_for_path(
            role="SUCCESSOR_CANDIDATE",
            label="TEST FIXTURE candidate",
            object_type="SUCCESSOR_CANDIDATE",
            path=paths["candidate"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="DELTA",
            label="TEST FIXTURE delta",
            object_type="DELTA",
            path=paths["delta"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="REOPENING_REGISTER",
            label="TEST FIXTURE reopening",
            object_type="REOPENING_REGISTER",
            path=paths["reopening"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="PRODUCT_MANIFEST",
            label="TEST FIXTURE products",
            object_type="PRODUCT_MANIFEST",
            path=paths["products"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="WITHHELD_CLAIMS",
            label="TEST FIXTURE withheld claims",
            object_type="CLAIM_SET",
            path=paths["claims"],
            storage_boundary="PUBLIC_GIT",
            boundary_root=public,
        ),
    ]
    scope = record_governance_scope_manifest(
        workspace,
        scope_label="TEST FIXTURE ONLY synthetic governance rehearsal",
        objects=objects,
        boundary_roots={"PUBLIC_GIT": public, "GENERATED_OUTPUT": generated, "ARCHIVE": archive},
        actor="synthetic-rehearsal",
    )["manifest"]
    return workspace, scope, candidate


def test_synthetic_rehearsal_exercises_full_stack_without_authority(tmp_path: Path) -> None:
    workspace, scope, candidate = _fixture(tmp_path)
    result = run_synthetic_governance_rehearsal(
        workspace,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        candidate=candidate,
        products=PRODUCTS,
    )
    certificate = result["certificate"]
    handoff = result["handoff_template"]

    assert certificate["execution_mode"] == REHEARSAL_EXECUTION_MODE
    assert certificate["record_type"] == REHEARSAL_RECORD_TYPE
    assert certificate["authoritative"] is False
    assert len(certificate["synthetic_opinion_records"]) == 7
    assert len(certificate["synthetic_disposition_records"]) == 3
    assert certificate["policy_evaluation_reference"]["release_readiness"] == "UNSATISFIED"
    assert certificate["release_readiness_package_reference"]["readiness_state"] == "NOT_READY"
    blocker_codes = certificate["release_readiness_package_reference"]["blocker_codes"]
    assert "GOVERNANCE_POLICY_UNSATISFIED" in blocker_codes
    assert "UNRESOLVED_RELEASE_BLOCKING_CONDITIONS" not in blocker_codes
    assert "release_blocking_condition_ids" not in certificate["release_readiness_package_reference"]
    assert certificate["authority_boundary_probe"]["attempted"] is True
    assert certificate["authority_boundary_probe"]["blocked"] is True
    assert "Synthetic or local execution" in certificate["authority_boundary_probe"]["error"]
    assert certificate["release_authorization_performed"] is False
    assert certificate["canonical_successor_authorized"] is False
    assert certificate["publication_authorized"] is False
    assert certificate["real_human_governance_completed"] is False
    assert len(certificate["required_real_human_actions"]) == 4

    assert handoff["record_type"] == REHEARSAL_RECORD_TYPE
    assert handoff["handoff_state"] == "TEMPLATE_ONLY_REAL_HUMAN_EXECUTION_DEFERRED"
    assert {item["track"] for item in handoff["tracks"]} == set(REVIEW_TRACKS)
    assert handoff["protected_evidence_included"] is False
    assert handoff["real_reviewer_records_included"] is False
    assert handoff["real_owner_dispositions_included"] is False
    assert handoff["real_release_authority_decision_included"] is False
    assert handoff["canonical_publication_authorized"] is False

    assert verify_governance_reviewer_opinions(workspace)["valid"] is True
    assert verify_governance_owner_dispositions(workspace)["valid"] is True
    assert load_governance_release_decisions(workspace) == []
    assert Path(result["certificate_path"]).is_file()
    assert Path(result["handoff_template_path"]).is_file()


def test_rehearsal_preserves_required_synthetic_semantic_states(tmp_path: Path) -> None:
    workspace, scope, candidate = _fixture(tmp_path)
    result = run_synthetic_governance_rehearsal(
        workspace,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        candidate=candidate,
        products=PRODUCTS,
    )
    opinions_root = workspace.root / "governance" / "opinions"
    records = [json.loads(path.read_text(encoding="utf-8")) for path in opinions_root.glob("*.json")]
    states = {record["opinion_state"] for record in records}
    assert {"SUPPORT", "OBJECT", "REQUEST_EVIDENCE", "ABSTAIN", "SUPPORT_WITH_CONDITIONS"} <= states
    evidence_request = next(record for record in records if record["opinion_state"] == "REQUEST_EVIDENCE")
    assert evidence_request["evidence_requests"] == [
        "TEST FIXTURE ONLY: supply additional evidence for the rehearsal branch."
    ]
    assert "conditions" not in evidence_request
    conditioned = next(record for record in records if record["opinion_state"] == "SUPPORT_WITH_CONDITIONS")
    assert conditioned["conditions"] == ["TEST FIXTURE ONLY: retain the synthetic domain condition for rehearsal."]
    assert "evidence_requests" not in conditioned
    security = [record for record in records if record["review_track"] == "SECURITY"]
    assert len(security) == 2
    assert any(record.get("supersedes_opinion_id") for record in security)

    disposition_root = workspace.root / "governance" / "owner-dispositions"
    dispositions = [json.loads(path.read_text(encoding="utf-8")) for path in disposition_root.glob("*.json")]
    assert {record["disposition_state"] for record in dispositions} == {
        "DEFER",
        "REQUEST_FURTHER_REVIEW",
        "ACCEPT_WITH_ACTION",
    }
    conditions = [condition for record in dispositions for condition in record["condition_register"]["conditions"]]
    assert any(
        condition["condition_id"] == "GOVCOND-00000000000000000000000000000001"
        and condition["release_effect"] == "BLOCKS_RELEASE"
        and condition["status"] == "OPEN"
        for condition in conditions
    )
    assert result["certificate"]["authoritative"] is False


def test_handoff_template_is_deterministic_and_contains_only_placeholders() -> None:
    kwargs = {
        "scope_id": "GOVSCOPE-TEST",
        "scope_sha256": "a" * 64,
        "candidate_reference": {
            "candidate_id": "SC-TEST",
            "candidate_sha256": "b" * 64,
            "candidate_artifact_sha256": "c" * 64,
            "scope_artifact_sha256": "c" * 64,
        },
        "policy_evaluation_reference": {
            "evaluation_id": "GOVEVAL-TEST",
            "evaluation_sha256": "d" * 64,
            "input_binding_sha256": "e" * 64,
            "policy_id": "GOVPOLICY-TEST",
            "policy_version": "1.0.0",
            "policy_sha256": "f" * 64,
        },
        "readiness_package_reference": {
            "package_id": "GOVREADY-TEST",
            "package_sha256": "1" * 64,
        },
    }
    first = build_handoff_template(**kwargs)
    second = build_handoff_template(**kwargs)
    assert first == second
    assert first["record_type"] == REHEARSAL_RECORD_TYPE
    assert first["template_sha256"] == second["template_sha256"]
    assert len(first["tracks"]) == 6
    for track in REVIEW_TRACKS:
        assert len(TRACK_QUESTIONS[track]) == 2
    serialized = json.dumps(first, sort_keys=True)
    assert "TEST FIXTURE ONLY" not in serialized
    assert "<REAL_REVIEWER_TO_BE_SUPPLIED_OUTSIDE_SYNTHETIC_REHEARSAL>" in serialized
    assert 'protected_evidence_included": false' in serialized


def test_handoff_template_never_embeds_real_governance_completion_claims() -> None:
    template = build_handoff_template(
        scope_id="GOVSCOPE-TEST",
        scope_sha256="a" * 64,
        candidate_reference={"candidate_id": "SC", "candidate_sha256": "b" * 64},
        policy_evaluation_reference={"evaluation_id": "GOVEVAL", "evaluation_sha256": "c" * 64},
        readiness_package_reference={"package_id": "GOVREADY", "package_sha256": "d" * 64},
    )
    assert template["real_reviewer_records_included"] is False
    assert template["real_owner_dispositions_included"] is False
    assert template["real_release_authority_decision_included"] is False
    assert template["canonical_publication_authorized"] is False
    assert all("REAL_REVIEWER" in item["identity_placeholder"] for item in template["tracks"])
