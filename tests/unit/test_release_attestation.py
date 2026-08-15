from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

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


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace.initialize(tmp_path / "workspace")


def _attest(
    workspace: Workspace,
    candidate: dict[str, Any],
    *,
    decision: str = "AUTHORIZE",
    blocked: str | None = None,
    conditions: list[dict[str, str]] | None = None,
    supersedes: str | None = None,
) -> dict[str, Any]:
    return record_release_attestation(
        workspace,
        candidate=candidate,
        products=PRODUCTS,
        track_assessments=_assessments(blocked=blocked),
        decision=decision,
        decision_rationale="TEST FIXTURE ONLY explicit release judgment.",
        conditions=conditions,
        supersedes_attestation_id=supersedes,
        actor="fraware",
    )["attestation"]


def test_policy_is_small_and_exact() -> None:
    policy = load_release_attestation_policy()
    assert policy["profile"] == "DEFAULT_RELEASE_ATTESTATION"
    assert policy["designated_authority_key"] == "fraware"
    assert set(policy["required_tracks"]) == set(REVIEW_TRACKS)
    assert len(release_attestation_policy_sha256()) == 64


def test_authorization_is_one_six_domain_attestation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    record = _attest(workspace, _candidate("v1.8-attested"))

    assert record["decision"] == "AUTHORIZE"
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
        record_attested_publication(
            workspace,
            attestation_id=record["attestation_id"],
            publication_evidence={"reference": "public-ref:test/release", "sha256": "b" * 64},
            actor="fraware",
        )


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


def test_all_six_domains_are_required_exactly_once(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    candidate = _candidate("v1.8-track-shape")
    missing = _assessments()[:-1]
    with pytest.raises(ValueError, match="each review domain exactly once"):
        record_release_attestation(
            workspace,
            candidate=candidate,
            products=PRODUCTS,
            track_assessments=missing,
            decision="AUTHORIZE",
            decision_rationale="TEST FIXTURE ONLY.",
            actor="fraware",
        )

    duplicate = _assessments()
    duplicate[-1] = dict(duplicate[0])
    with pytest.raises(ValueError, match="each review domain exactly once"):
        record_release_attestation(
            workspace,
            candidate=candidate,
            products=PRODUCTS,
            track_assessments=duplicate,
            decision="AUTHORIZE",
            decision_rationale="TEST FIXTURE ONLY.",
            actor="fraware",
        )


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


def test_correction_supersedes_same_exact_object(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    candidate = _candidate("v1.8-correction")
    first = _attest(workspace, candidate, decision="WITHHOLD")
    second = _attest(workspace, candidate, supersedes=first["attestation_id"])

    report = verify_release_attestations(workspace)
    assert report["valid"] is True
    assert report["record_count"] == 2
    assert report["active_count"] == 1
    assert second["supersedes_attestation_id"] == first["attestation_id"]


def test_supersession_cannot_cross_candidate_bytes(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    first = _attest(workspace, _candidate("v1.8-first"), decision="WITHHOLD")
    with pytest.raises(ValueError, match="same exact object"):
        _attest(
            workspace,
            _candidate("v1.8-second"),
            supersedes=first["attestation_id"],
        )


def test_publication_is_separate_and_single(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    attestation = _attest(workspace, _candidate("v1.8-published"))
    publication = record_attested_publication(
        workspace,
        attestation_id=attestation["attestation_id"],
        publication_evidence={"reference": "public-ref:test/release", "sha256": "b" * 64},
        actor="fraware",
    )["publication"]

    assert publication["automatic_publication_performed"] is False
    assert publication["attestation_reference"]["attestation_sha256"] == attestation["attestation_sha256"]
    assert verify_attested_publications(workspace)["valid"] is True
    assert len(load_attested_publications(workspace)) == 1

    with pytest.raises(ValueError, match="already has a publication"):
        record_attested_publication(
            workspace,
            attestation_id=attestation["attestation_id"],
            publication_evidence={"reference": "public-ref:test/release-2", "sha256": "c" * 64},
            actor="fraware",
        )


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


def test_tampering_is_detected(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _attest(workspace, _candidate("v1.8-tamper"))
    attestation_path = Path(load_release_attestations(workspace)[0]["_path"])
    value = json.loads(attestation_path.read_text(encoding="utf-8"))
    value["decision_rationale"] = "tampered"
    attestation_path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    assert verify_release_attestations(workspace)["valid"] is False

    clean = Workspace.initialize(tmp_path / "clean")
    authorized = _attest(clean, _candidate("v1.8-pub-tamper"))
    record_attested_publication(
        clean,
        attestation_id=authorized["attestation_id"],
        publication_evidence={"reference": "public-ref:test/release", "sha256": "b" * 64},
        actor="fraware",
    )
    publication_path = Path(load_attested_publications(clean)[0]["_path"])
    publication_value = json.loads(publication_path.read_text(encoding="utf-8"))
    publication_value["publication_evidence"]["reference"] = "public-ref:tampered"
    publication_path.write_text(json.dumps(publication_value, indent=2) + "\n", encoding="utf-8")
    assert verify_attested_publications(clean)["valid"] is False
