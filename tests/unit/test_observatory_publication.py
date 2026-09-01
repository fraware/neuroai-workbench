from __future__ import annotations

import json
import shutil

import pytest

from neuroai_workbench.observatory_publication import (
    AUTHORIZATION_BOUNDARY,
    PUBLICATION_BOUNDARY,
    ObservatoryPublicationError,
    record_s2_authorization,
    record_s2_publication,
    verify_s2_authorizations,
    verify_s2_publication_binding,
)
from neuroai_workbench.observatory_s2_release import OBJECT_FILES, S2_CANDIDATE_BOUNDARY
from neuroai_workbench.util import canonical_json_bytes, sha256_bytes


def _json(path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _candidate(root, *, release_tag="candidate", entity_id="ORG-1"):
    records = root / "records"
    records.mkdir(parents=True, exist_ok=True)
    file_entries = []
    for filename in OBJECT_FILES:
        payload = b""
        if filename == "entities.jsonl":
            payload = f'{{"object_class":"Entity","entity_id":"{entity_id}"}}\n'.encode()
        path = records / filename
        path.write_bytes(payload)
        file_entries.append({"path": f"records/{filename}", "sha256": sha256_bytes(payload)})
    file_entries.sort(key=lambda item: item["path"])
    content_sha = sha256_bytes(canonical_json_bytes(file_entries))
    candidate_id = f"OBS-V2-CAND-{content_sha[:20].upper()}"
    descriptor = {
        "schema_version": "1",
        "release_type": "OBSERVATORY_V2_S2_CANDIDATE",
        "release_tag": release_tag,
        "candidate_id": candidate_id,
        "state": "NONCANONICAL_CANDIDATE",
        "canonical_publication_state": "NOT_AUTHORIZED",
        "release_authorized": False,
        "published": False,
        "record_counts": {
            "Entity": 1,
            "Source": 0,
            "Observation": 0,
            "Assertion": 0,
            "Event": 0,
            "Relationship": 0,
            "Candidate": 0,
            "ReopeningDecision": 0,
        },
        "candidate_content_sha256": content_sha,
        "workbench_compatibility_version": "0.3.0.dev0",
        "producer_workbench_commit": "1" * 40,
        "runtime_execution_pin": "2" * 40,
        "observatory_graph_schema_version": "1",
        "s2_predecessor": {"release_tag": "prior", "commit": "3" * 40},
        "migration_proof": {
            "field_proof_sha256": "4" * 64,
            "gate_a_manifest_sha256": "5" * 64,
            "gate_a_descriptor_sha256": "6" * 64,
            "native_candidate_manifest_sha256": "7" * 64,
        },
        "boundary": S2_CANDIDATE_BOUNDARY,
    }
    descriptor_sha = sha256_bytes(canonical_json_bytes(descriptor))
    manifest = {
        "schema_version": "1",
        "candidate_id": candidate_id,
        "candidate_content_sha256": content_sha,
        "files": file_entries,
        "descriptor_sha256": descriptor_sha,
        "release_authorized": False,
        "published": False,
        "boundary": S2_CANDIDATE_BOUNDARY,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    _json(root / "descriptor.json", descriptor)
    _json(root / "manifest.json", manifest)
    return root


def test_authorize_then_publish_exact_candidate(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    authorization = record_s2_authorization(
        release,
        decision="AUTHORIZE",
        decision_rationale="Publish exact mechanically verified candidate.",
        recorded_at="2026-09-01T08:00:00Z",
    )["authorization"]
    assert authorization["decision"] == "AUTHORIZE"
    assert authorization["boundary"] == AUTHORIZATION_BOUNDARY
    assert verify_s2_authorizations(release)["valid"] is True

    publication = record_s2_publication(
        release,
        publication_evidence={"reference": "public-ref:github-release:candidate", "sha256": "8" * 64},
        recorded_at="2026-09-01T08:01:00Z",
    )["publication"]
    assert publication["boundary"] == PUBLICATION_BOUNDARY
    report = verify_s2_publication_binding(release)
    assert report["valid"] is True
    assert report["authorization_id"] == authorization["authorization_id"]
    assert report["publication_id"] == publication["publication_id"]


def test_withhold_cannot_publish(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    record_s2_authorization(
        release,
        decision="WITHHOLD",
        decision_rationale="Not ready.",
        recorded_at="2026-09-01T08:00:00Z",
    )
    with pytest.raises(ObservatoryPublicationError, match="active AUTHORIZE"):
        record_s2_publication(
            release,
            publication_evidence={"reference": "public-ref:test", "sha256": "8" * 64},
        )
    assert verify_s2_publication_binding(release)["valid"] is False


def test_authorization_without_publication_is_not_published(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    record_s2_authorization(
        release,
        decision="AUTHORIZE",
        decision_rationale="Authorized but not yet published.",
    )
    report = verify_s2_publication_binding(release)
    assert report["valid"] is False
    assert any("publication.json" in error for error in report["errors"])


def test_authorization_supersession_changes_decision_without_changing_candidate(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    first = record_s2_authorization(
        release,
        decision="AUTHORIZE",
        decision_rationale="Initial decision.",
    )["authorization"]
    second = record_s2_authorization(
        release,
        decision="WITHHOLD",
        decision_rationale="Withhold before publication.",
        supersedes_authorization_id=first["authorization_id"],
    )["authorization"]
    report = verify_s2_authorizations(release)
    assert report["valid"] is True
    assert report["active_count"] == 1
    with pytest.raises(ObservatoryPublicationError, match="active AUTHORIZE"):
        record_s2_publication(
            release,
            publication_evidence={"reference": "public-ref:test", "sha256": "8" * 64},
        )
    assert second["decision"] == "WITHHOLD"


def test_published_authorization_cannot_be_superseded(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    authorization = record_s2_authorization(
        release,
        decision="AUTHORIZE",
        decision_rationale="Authorize.",
    )["authorization"]
    record_s2_publication(
        release,
        publication_evidence={"reference": "public-ref:test", "sha256": "8" * 64},
    )
    with pytest.raises(ObservatoryPublicationError, match="published S2 release is immutable"):
        record_s2_authorization(
            release,
            decision="WITHHOLD",
            decision_rationale="Too late.",
            supersedes_authorization_id=authorization["authorization_id"],
        )


def test_candidate_digest_substitution_invalidates_published_binding(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    record_s2_authorization(release, decision="AUTHORIZE", decision_rationale="Authorize.")
    record_s2_publication(
        release,
        publication_evidence={"reference": "public-ref:test", "sha256": "8" * 64},
    )
    with (release / "records" / "entities.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{"object_class":"Entity","entity_id":"ORG-TAMPER"}\n')
    report = verify_s2_publication_binding(release)
    assert report["valid"] is False
    assert any("candidate is invalid" in error for error in report["errors"])


def test_publication_copied_to_wrong_candidate_fails_binding(tmp_path) -> None:
    first = _candidate(tmp_path / "first", release_tag="first", entity_id="ORG-1")
    record_s2_authorization(first, decision="AUTHORIZE", decision_rationale="Authorize first.")
    record_s2_publication(
        first,
        publication_evidence={"reference": "public-ref:first", "sha256": "8" * 64},
    )

    second = _candidate(tmp_path / "second", release_tag="second", entity_id="ORG-2")
    shutil.copytree(first / "governance", second / "governance")
    report = verify_s2_publication_binding(second)
    assert report["valid"] is False
    assert any("candidate binding mismatch" in error for error in report["errors"])


def test_manual_candidate_authority_boolean_is_rejected(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    descriptor = json.loads((release / "descriptor.json").read_text(encoding="utf-8"))
    descriptor["release_authorized"] = True
    _json(release / "descriptor.json", descriptor)
    report = verify_s2_authorizations(release)
    assert report["valid"] is False
    assert any("candidate is invalid" in error for error in report["errors"])
