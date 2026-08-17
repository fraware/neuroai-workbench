from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import neuroai_workbench.release_attestation as release_module
from neuroai_workbench.governance_opinions import REVIEW_TRACKS
from neuroai_workbench.release_attestation import (
    load_attested_publications,
    load_release_attestation_policy,
    load_release_attestations,
    record_attested_publication,
    record_release_attestation,
    release_attestation_policy_sha256,
    verify_attested_publications,
    verify_release_attestations,
)
from neuroai_workbench.successor import generate_from_observatory_release
from neuroai_workbench.workspace import Workspace

ROOT = Path(__file__).resolve().parents[2]
SUCCESSOR = ROOT / "examples" / "observatory" / "canonical_successor_snapshot_v1.7.json"
PRODUCTS = [{"product_id": "public-projection", "sha256": "a" * 64}]


def _candidate(version: str) -> dict[str, Any]:
    return generate_from_observatory_release(SUCCESSOR, version=version, actor="test-fixture")


def _assessments(*, blocked: str | None = None) -> list[dict[str, str]]:
    return [
        {
            "track": track,
            "state": "BLOCK" if track == blocked else "PASS",
            "rationale": f"TEST FIXTURE ONLY judgment for {track}.",
        }
        for track in sorted(REVIEW_TRACKS)
    ]


def _workspace(tmp_path: Path, name: str = "workspace") -> Workspace:
    return Workspace.initialize(tmp_path / name)


def _attest(
    workspace: Workspace,
    candidate: dict[str, Any],
    *,
    decision: str = "AUTHORIZE",
    blocked: str | None = None,
    conditions: list[dict[str, str]] | None = None,
    products: list[dict[str, str]] | None = None,
    supersedes: str | None = None,
) -> dict[str, Any]:
    return record_release_attestation(
        workspace,
        candidate=candidate,
        products=PRODUCTS if products is None else products,
        track_assessments=_assessments(blocked=blocked),
        decision=decision,
        decision_rationale="TEST FIXTURE ONLY explicit release judgment.",
        conditions=conditions,
        supersedes_attestation_id=supersedes,
        actor="fraware",
    )["attestation"]


def _publish(workspace: Workspace, attestation_id: str, suffix: str = "release") -> dict[str, Any]:
    return record_attested_publication(
        workspace,
        attestation_id=attestation_id,
        publication_evidence={"reference": f"public-ref:test/{suffix}", "sha256": "b" * 64},
        actor="fraware",
    )["publication"]


def test_policy_is_small_exact_and_names_serialization_contract() -> None:
    policy = load_release_attestation_policy()
    assert policy["profile"] == "DEFAULT_RELEASE_ATTESTATION"
    assert policy["designated_authority_key"] == "fraware"
    assert policy["candidate_serialization"] == "JSON_UTF8_INDENT2_LF"
    assert set(policy["required_tracks"]) == set(REVIEW_TRACKS)
    assert len(release_attestation_policy_sha256()) == 64


def test_policy_loader_rejects_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    original = release_module._resource

    def drifted(name: str) -> dict[str, Any]:
        value = original(name)
        if name == release_module.POLICY_RESOURCE:
            value["designated_authority_key"] = "other"
        return value

    monkeypatch.setattr(release_module, "_resource", drifted)
    with pytest.raises(ValueError, match="policy is invalid"):
        load_release_attestation_policy()


def test_policy_loader_rejects_track_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    original = release_module._resource

    def drifted(name: str) -> dict[str, Any]:
        value = original(name)
        if name == release_module.POLICY_RESOURCE:
            value["required_tracks"] = ["SECURITY"]
        return value

    monkeypatch.setattr(release_module, "_resource", drifted)
    with pytest.raises(ValueError, match="exactly the six"):
        load_release_attestation_policy()


def test_authorization_is_one_six_domain_attestation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    record = _attest(workspace, _candidate("v1.8-attested"))

    assert record["decision"] == "AUTHORIZE"
    assert record["candidate_reference"]["candidate_serialization"] == "JSON_UTF8_INDENT2_LF"
    assert len(record["candidate_reference"]["candidate_serialized_sha256"]) == 64
    assert len(record["track_assessments"]) == 6
    assert {item["state"] for item in record["track_assessments"]} == {"PASS"}
    assert record["conditions"] == []
    assert verify_release_attestations(workspace)["valid"] is True
    assert len(load_release_attestations(workspace)) == 1


def test_withhold_is_first_class_and_cannot_publish(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    record = _attest(
        workspace,
        _candidate("v1.8-withheld"),
        decision="WITHHOLD",
        blocked="SECURITY",
    )

    assert record["decision"] == "WITHHOLD"
    assert verify_release_attestations(workspace)["valid"] is True
    with pytest.raises(ValueError, match="active AUTHORIZE"):
        _publish(workspace, record["attestation_id"])


def test_authorize_fails_closed_on_track_or_condition_blocker(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    candidate = _candidate("v1.8-blocked")
    with pytest.raises(ValueError, match="review domain is BLOCK"):
        _attest(workspace, candidate, blocked="METHODOLOGY")

    condition = {
        "condition_id": "COND-1",
        "status": "OPEN",
        "release_effect": "BLOCKS_RELEASE",
        "summary": "TEST FIXTURE ONLY unresolved blocker.",
    }
    with pytest.raises(ValueError, match="unresolved release blocker"):
        _attest(workspace, candidate, conditions=[condition])
    assert load_release_attestations(workspace) == []


def test_nonblocking_and_resolved_conditions_are_admitted(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    conditions = [
        {
            "condition_id": "COND-2",
            "status": "RESOLVED",
            "release_effect": "BLOCKS_RELEASE",
            "summary": "TEST FIXTURE ONLY resolved blocker.",
        },
        {
            "condition_id": "COND-1",
            "status": "OPEN",
            "release_effect": "NON_BLOCKING",
            "summary": "TEST FIXTURE ONLY visible residual.",
        },
    ]
    record = _attest(workspace, _candidate("v1.8-conditions"), conditions=conditions)
    assert [item["condition_id"] for item in record["conditions"]] == ["COND-1", "COND-2"]


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda items: items[:-1], "each review domain exactly once"),
        (lambda items: items[:-1] + [dict(items[0])], "each review domain exactly once"),
        (
            lambda items: [{**item, "state": "UNKNOWN"} if index == 0 else item for index, item in enumerate(items)],
            "requires PASS/BLOCK",
        ),
        (
            lambda items: [{**item, "rationale": ""} if index == 0 else item for index, item in enumerate(items)],
            "requires PASS/BLOCK",
        ),
    ],
)
def test_assessment_shape_fails_closed(tmp_path: Path, mutator: Any, message: str) -> None:
    workspace = _workspace(tmp_path)
    with pytest.raises(ValueError, match=message):
        record_release_attestation(
            workspace,
            candidate=_candidate("v1.8-track-shape"),
            products=PRODUCTS,
            track_assessments=mutator(_assessments()),
            decision="AUTHORIZE",
            decision_rationale="TEST FIXTURE ONLY.",
            actor="fraware",
        )


@pytest.mark.parametrize(
    ("products", "message"),
    [
        ([], "At least one product"),
        ([{"product_id": "", "sha256": "a" * 64}], "non-empty and unique"),
        (
            [
                {"product_id": "same", "sha256": "a" * 64},
                {"product_id": "same", "sha256": "b" * 64},
            ],
            "non-empty and unique",
        ),
        ([{"product_id": "bad", "sha256": "ABC"}], "lowercase SHA-256"),
    ],
)
def test_product_shape_fails_closed(tmp_path: Path, products: list[dict[str, str]], message: str) -> None:
    workspace = _workspace(tmp_path)
    with pytest.raises(ValueError, match=message):
        _attest(workspace, _candidate("v1.8-product-shape"), products=products)


@pytest.mark.parametrize(
    ("conditions", "message"),
    [
        ([{"condition_id": "", "status": "OPEN", "release_effect": "NON_BLOCKING", "summary": "x"}], "non-empty"),
        (
            [
                {"condition_id": "C", "status": "OPEN", "release_effect": "NON_BLOCKING", "summary": "x"},
                {"condition_id": "C", "status": "RESOLVED", "release_effect": "NON_BLOCKING", "summary": "x"},
            ],
            "non-empty and unique",
        ),
        ([{"condition_id": "C", "status": "BAD", "release_effect": "NON_BLOCKING", "summary": "x"}], "invalid"),
        ([{"condition_id": "C", "status": "OPEN", "release_effect": "BAD", "summary": "x"}], "invalid"),
        ([{"condition_id": "C", "status": "OPEN", "release_effect": "NON_BLOCKING", "summary": ""}], "invalid"),
    ],
)
def test_condition_shape_fails_closed(
    tmp_path: Path,
    conditions: list[dict[str, str]],
    message: str,
) -> None:
    workspace = _workspace(tmp_path)
    with pytest.raises(ValueError, match=message):
        _attest(workspace, _candidate("v1.8-condition-shape"), conditions=conditions)


def test_only_designated_authority_can_attest(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with pytest.raises(ValueError, match="designated authority fraware"):
        record_release_attestation(
            workspace,
            candidate=_candidate("v1.8-wrong-actor"),
            products=PRODUCTS,
            track_assessments=_assessments(),
            decision="AUTHORIZE",
            decision_rationale="TEST FIXTURE ONLY.",
            actor="other-human",
        )
    assert load_release_attestations(workspace) == []


def test_invalid_decision_or_empty_rationale_is_rejected(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    candidate = _candidate("v1.8-decision")
    with pytest.raises(ValueError, match="AUTHORIZE/WITHHOLD"):
        record_release_attestation(
            workspace,
            candidate=candidate,
            products=PRODUCTS,
            track_assessments=_assessments(),
            decision="MAYBE",
            decision_rationale="TEST FIXTURE ONLY.",
            actor="fraware",
        )
    with pytest.raises(ValueError, match="AUTHORIZE/WITHHOLD"):
        record_release_attestation(
            workspace,
            candidate=candidate,
            products=PRODUCTS,
            track_assessments=_assessments(),
            decision="WITHHOLD",
            decision_rationale=" ",
            actor="fraware",
        )


def test_invalid_successor_fails_before_write(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with pytest.raises(ValueError, match="Successor candidate failed validation"):
        record_release_attestation(
            workspace,
            candidate={"not": "a successor"},
            products=PRODUCTS,
            track_assessments=_assessments(),
            decision="WITHHOLD",
            decision_rationale="TEST FIXTURE ONLY.",
            actor="fraware",
        )
    assert load_release_attestations(workspace) == []


def test_correction_supersedes_same_exact_representation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    candidate = _candidate("v1.8-correction")
    first = _attest(workspace, candidate, decision="WITHHOLD")
    second = _attest(workspace, candidate, supersedes=first["attestation_id"])

    report = verify_release_attestations(workspace)
    assert report["valid"] is True
    assert report["record_count"] == 2
    assert report["active_count"] == 1
    assert second["supersedes_attestation_id"] == first["attestation_id"]


def test_duplicate_active_attestation_requires_explicit_supersession(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    candidate = _candidate("v1.8-duplicate")
    _attest(workspace, candidate, decision="WITHHOLD")
    with pytest.raises(ValueError, match="already has an active attestation"):
        _attest(workspace, candidate, decision="WITHHOLD")


def test_supersession_cannot_cross_candidate_representation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    first = _attest(workspace, _candidate("v1.8-first"), decision="WITHHOLD")
    with pytest.raises(ValueError, match="same exact object"):
        _attest(
            workspace,
            _candidate("v1.8-second"),
            supersedes=first["attestation_id"],
        )


def test_published_attestation_is_frozen(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    candidate = _candidate("v1.8-published-frozen")
    attestation = _attest(workspace, candidate)
    _publish(workspace, attestation["attestation_id"])

    with pytest.raises(ValueError, match="Published attestation is immutable"):
        _attest(workspace, candidate, decision="WITHHOLD", supersedes=attestation["attestation_id"])

    assert verify_release_attestations(workspace)["valid"] is True
    assert verify_attested_publications(workspace)["valid"] is True


def test_publication_is_separate_and_single(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    attestation = _attest(workspace, _candidate("v1.8-published"))
    publication = _publish(workspace, attestation["attestation_id"])

    assert publication["automatic_publication_performed"] is False
    assert publication["attestation_reference"]["attestation_sha256"] == attestation["attestation_sha256"]
    assert publication["candidate_reference"]["candidate_serialization"] == "JSON_UTF8_INDENT2_LF"
    assert verify_attested_publications(workspace)["valid"] is True
    assert len(load_attested_publications(workspace)) == 1

    with pytest.raises(ValueError, match="already has a publication"):
        _publish(workspace, attestation["attestation_id"], "release-2")


def test_publication_rejects_wrong_actor_and_bad_evidence(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    attestation = _attest(workspace, _candidate("v1.8-pub-guard"))
    with pytest.raises(ValueError, match="designated authority fraware"):
        record_attested_publication(
            workspace,
            attestation_id=attestation["attestation_id"],
            publication_evidence={"reference": "public-ref:test/release", "sha256": "b" * 64},
            actor="other-human",
        )
    with pytest.raises(ValueError, match="non-empty public-ref"):
        record_attested_publication(
            workspace,
            attestation_id=attestation["attestation_id"],
            publication_evidence={"reference": "public-ref:", "sha256": "b" * 64},
            actor="fraware",
        )
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        record_attested_publication(
            workspace,
            attestation_id=attestation["attestation_id"],
            publication_evidence={"reference": "public-ref:test/release", "sha256": "bad"},
            actor="fraware",
        )


def test_tampering_is_detected_and_blocks_followup_writes(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _attest(workspace, _candidate("v1.8-tamper"))
    attestation_path = Path(load_release_attestations(workspace)[0]["_path"])
    value = json.loads(attestation_path.read_text(encoding="utf-8"))
    value["decision_rationale"] = "tampered"
    attestation_path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    assert verify_release_attestations(workspace)["valid"] is False
    with pytest.raises(ValueError, match="store is invalid"):
        _attest(workspace, _candidate("v1.8-after-tamper"), decision="WITHHOLD")


def test_publication_tampering_is_detected_and_blocks_new_attestation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    authorized = _attest(workspace, _candidate("v1.8-pub-tamper"))
    _publish(workspace, authorized["attestation_id"])
    publication_path = Path(load_attested_publications(workspace)[0]["_path"])
    publication_value = json.loads(publication_path.read_text(encoding="utf-8"))
    publication_value["publication_evidence"]["reference"] = "public-ref:tampered"
    publication_path.write_text(json.dumps(publication_value, indent=2) + "\n", encoding="utf-8")
    assert verify_attested_publications(workspace)["valid"] is False
    with pytest.raises(ValueError, match="Attested-publication store is invalid"):
        _attest(workspace, _candidate("v1.8-after-pub-tamper"), decision="WITHHOLD")


def test_verifier_recomputes_authorization_semantics() -> None:
    record = {
        "attestation_id": "RELATT-TEST",
        "decision": "AUTHORIZE",
        "decision_rationale": "x",
        "products": PRODUCTS,
        "track_assessments": _assessments(blocked="SECURITY"),
        "conditions": [],
        "candidate_reference": {
            "candidate_sha256": "a" * 64,
            "candidate_serialization": "JSON_UTF8_INDENT2_LF",
            "candidate_serialized_sha256": "b" * 64,
        },
    }
    errors = release_module._semantic_errors(record)
    assert any("blocking review domain" in error for error in errors)

    record["track_assessments"] = _assessments()
    record["conditions"] = [
        {
            "condition_id": "C",
            "status": "OPEN",
            "release_effect": "BLOCKS_RELEASE",
            "summary": "x",
        }
    ]
    errors = release_module._semantic_errors(record)
    assert any("unresolved release blocker" in error for error in errors)


def test_verifier_recomputes_canonical_order_and_serialization() -> None:
    record = {
        "attestation_id": "RELATT-TEST",
        "decision": "WITHHOLD",
        "decision_rationale": "x",
        "products": list(
            reversed(
                [
                    {"product_id": "a", "sha256": "a" * 64},
                    {"product_id": "b", "sha256": "b" * 64},
                ]
            )
        ),
        "track_assessments": list(reversed(_assessments())),
        "conditions": list(
            reversed(
                [
                    {"condition_id": "A", "status": "OPEN", "release_effect": "NON_BLOCKING", "summary": "a"},
                    {"condition_id": "B", "status": "RESOLVED", "release_effect": "NON_BLOCKING", "summary": "b"},
                ]
            )
        ),
        "candidate_reference": {
            "candidate_sha256": "a" * 64,
            "candidate_serialization": "BAD",
            "candidate_serialized_sha256": "b" * 64,
        },
    }
    errors = release_module._semantic_errors(record)
    assert any("products are not in canonical order" in error for error in errors)
    assert any("track assessments are not in canonical order" in error for error in errors)
    assert any("conditions are not in canonical order" in error for error in errors)
    assert any("serialization contract mismatch" in error for error in errors)


def test_private_normalizers_reject_non_object_entries() -> None:
    with pytest.raises(ValueError, match="Product entries"):
        release_module._products(["bad"])
    with pytest.raises(ValueError, match="assessments must be objects"):
        release_module._assessments(["bad"])
    with pytest.raises(ValueError, match="Condition entries"):
        release_module._conditions(["bad"])
    with pytest.raises(ValueError, match="Conditions must be a list"):
        release_module._conditions("bad")
    with pytest.raises(ValueError, match="assessments must be a list"):
        release_module._assessments("bad")


def test_semantic_verifier_rejects_bad_candidate_reference() -> None:
    base = {
        "attestation_id": "RELATT-TEST",
        "decision": "WITHHOLD",
        "decision_rationale": "x",
        "products": PRODUCTS,
        "track_assessments": _assessments(),
        "conditions": [],
    }
    errors = release_module._semantic_errors({**base, "candidate_reference": None})
    assert any("candidate reference is invalid" in error for error in errors)

    errors = release_module._semantic_errors(
        {
            **base,
            "candidate_reference": {
                "candidate_sha256": "bad",
                "candidate_serialization": "JSON_UTF8_INDENT2_LF",
                "candidate_serialized_sha256": "b" * 64,
            },
        }
    )
    assert any("lowercase SHA-256" in error for error in errors)


def test_supersession_cycle_helper() -> None:
    index = {
        "A": {"supersedes_attestation_id": "B"},
        "B": {"supersedes_attestation_id": "A"},
    }
    assert release_module._supersession_cycle(index, "A") is True
    assert release_module._supersession_cycle({"A": {}}, "A") is False
    assert release_module._supersession_cycle({}, "missing") is False


def test_duplicate_record_ids_fail_verification(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    root = workspace.root / "governance" / "release-attestations"
    root.mkdir(parents=True, exist_ok=True)
    first = {"attestation_id": "RELATT-DUP"}
    (root / "a.json").write_text(json.dumps(first), encoding="utf-8")
    (root / "b.json").write_text(json.dumps(first), encoding="utf-8")
    report = verify_release_attestations(workspace)
    assert report["valid"] is False
    assert "Duplicate attestation_id" in report["errors"]


def test_non_object_record_fails_loading(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    root = workspace.root / "governance" / "release-attestations"
    root.mkdir(parents=True, exist_ok=True)
    (root / "bad.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must be an object"):
        load_release_attestations(workspace)
