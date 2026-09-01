from __future__ import annotations

import json
import shutil

import pytest

import neuroai_workbench.observatory_publication as publication_module
from neuroai_workbench.observatory_publication import (
    AUTHORIZATION_BOUNDARY,
    PUBLICATION_BOUNDARY,
    ObservatoryPublicationError,
    load_s2_authorizations,
    load_s2_publication,
    record_s2_authorization,
    record_s2_publication,
    verify_s2_authorizations,
    verify_s2_publication_binding,
)
from neuroai_workbench.observatory_s2_release import (
    CANDIDATE_FILE_PATHS,
    OBJECT_FILES,
    S2_CANDIDATE_BOUNDARY,
)
from neuroai_workbench.util import canonical_json_bytes, sha256_bytes


def _json(path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _candidate(root):
    records = root / "records"
    migration = root / "migration"
    records.mkdir(parents=True, exist_ok=True)
    migration.mkdir(parents=True, exist_ok=True)
    frozen = {
        "V14": "a" * 64,
        "V16": "b" * 64,
        "DELTA16": "c" * 64,
        "V17": "d" * 64,
        "PRIMA17": "e" * 64,
        "SOURCE_REGISTER14": "f" * 64,
        "MONITOR15": "0" * 64,
    }
    gate_descriptor = {
        "release_authorized": False,
        "representational_scope_complete": True,
        "workbench_compatibility_version": "0.3.0.dev0",
        "producer_workbench_commit": "1" * 40,
        "runtime_execution_pin": "2" * 40,
        "observatory_graph_schema_version": "1",
        "s2_predecessor_commit": "3" * 40,
        "inputs": frozen,
    }
    descriptor_sha = sha256_bytes(canonical_json_bytes(gate_descriptor))
    gate_manifest = {"descriptor_sha256": descriptor_sha, "release_authorized": False}
    gate_manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(gate_manifest))
    decision = {
        "schema_version": "1",
        "decision_type": "OBSERVATORY_V2_GATE_A_MECHANICAL_DECISION",
        "decision": "PASS_REPRESENTATIONAL_MIGRATION_MECHANICALLY_COMPLETE",
        "gate_a_complete": True,
        "release_authorized": False,
        "representational_scope_complete": True,
        "native_v2_materialization_complete": False,
        "field_proof_sha256": "4" * 64,
        "gate_a_package_manifest_sha256": gate_manifest["manifest_sha256"],
        "gate_a_package_descriptor_sha256": descriptor_sha,
        "producer_workbench_commit": "1" * 40,
        "runtime_execution_pin": "2" * 40,
        "s2_predecessor_commit": "3" * 40,
        "observatory_graph_schema_version": "1",
        "boundary": "mechanical test decision",
    }
    decision["decision_sha256"] = sha256_bytes(canonical_json_bytes(decision))
    _json(migration / "gate-a-descriptor.json", gate_descriptor)
    _json(migration / "gate-a-manifest.json", gate_manifest)
    _json(migration / "gate-a-decision.json", decision)

    for filename in OBJECT_FILES:
        payload = b'{"object_class":"Entity","entity_id":"ORG-1"}\n' if filename == "entities.jsonl" else b""
        (records / filename).write_bytes(payload)
    for relative in sorted(CANDIDATE_FILE_PATHS):
        path = root / relative
        if not path.exists():
            _json(path, {})

    files = [
        {"path": relative, "sha256": sha256_bytes((root / relative).read_bytes())}
        for relative in sorted(CANDIDATE_FILE_PATHS)
    ]
    content_sha = sha256_bytes(canonical_json_bytes(files))
    candidate_id = f"OBS-V2-CAND-{content_sha[:20].upper()}"
    descriptor = {
        "schema_version": "1",
        "release_type": "OBSERVATORY_V2_S2_CANDIDATE",
        "release_tag": "candidate",
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
        "frozen_inputs": frozen,
        "migration_proof": {
            "field_proof_sha256": decision["field_proof_sha256"],
            "gate_a_decision_sha256": decision["decision_sha256"],
            "gate_a_manifest_sha256": gate_manifest["manifest_sha256"],
            "gate_a_descriptor_sha256": gate_manifest["descriptor_sha256"],
            "native_candidate_manifest_sha256": "7" * 64,
        },
        "boundary": S2_CANDIDATE_BOUNDARY,
    }
    manifest = {
        "schema_version": "1",
        "candidate_id": candidate_id,
        "candidate_content_sha256": content_sha,
        "files": files,
        "descriptor_sha256": sha256_bytes(canonical_json_bytes(descriptor)),
        "release_authorized": False,
        "published": False,
        "boundary": S2_CANDIDATE_BOUNDARY,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    _json(root / "descriptor.json", descriptor)
    _json(root / "manifest.json", manifest)
    return root


def _auth_path(release):
    return next((release / "governance" / "authorizations").glob("*.json"))


def _rewrite_authorization(release, mutate):
    path = _auth_path(release)
    record = json.loads(path.read_text(encoding="utf-8"))
    mutate(record)
    record["authorization_sha256"] = publication_module._digest_record(record, "authorization_sha256")
    _json(path, record)
    return record


def _rewrite_publication(release, mutate):
    path = release / "governance" / "publication.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    mutate(record)
    record["publication_sha256"] = publication_module._digest_record(record, "publication_sha256")
    _json(path, record)
    return record


def test_operator_and_input_guards_fail_closed(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    with pytest.raises(ObservatoryPublicationError, match="authorization actor"):
        record_s2_authorization(
            release,
            decision="AUTHORIZE",
            decision_rationale="No.",
            actor="other",
        )
    with pytest.raises(ObservatoryPublicationError, match="AUTHORIZE/WITHHOLD"):
        record_s2_authorization(release, decision="UNKNOWN", decision_rationale="No.")
    with pytest.raises(ObservatoryPublicationError, match="AUTHORIZE/WITHHOLD"):
        record_s2_authorization(release, decision="AUTHORIZE", decision_rationale="   ")

    authorization = record_s2_authorization(
        release,
        decision="AUTHORIZE",
        decision_rationale="Exact candidate.",
    )["authorization"]
    with pytest.raises(ObservatoryPublicationError, match="already has an active authorization"):
        record_s2_authorization(release, decision="WITHHOLD", decision_rationale="Duplicate active decision.")
    with pytest.raises(ObservatoryPublicationError, match="supersession must target"):
        record_s2_authorization(
            release,
            decision="WITHHOLD",
            decision_rationale="Wrong target.",
            supersedes_authorization_id="OBSAUTH-NOT-ACTIVE",
        )
    assert authorization["authorization_id"]

    with pytest.raises(ObservatoryPublicationError, match="publication actor"):
        record_s2_publication(
            release,
            publication_evidence={"reference": "public-ref:test", "sha256": "8" * 64},
            actor="other",
        )
    with pytest.raises(ObservatoryPublicationError, match="non-empty public-ref"):
        record_s2_publication(
            release,
            publication_evidence={"reference": "public-ref:", "sha256": "8" * 64},
        )
    with pytest.raises(ObservatoryPublicationError, match="publication evidence sha256"):
        record_s2_publication(
            release,
            publication_evidence={"reference": "public-ref:test", "sha256": "bad"},
        )


def test_authorization_semantic_corruption_is_detected(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    record_s2_authorization(release, decision="AUTHORIZE", decision_rationale="Valid.")

    def corrupt(record) -> None:
        record["recorded_by"] = "other"
        record["decision"] = "UNKNOWN"
        record["decision_rationale"] = ""
        record["candidate_reference"] = {"candidate_id": "OTHER"}
        record["boundary"] = "wrong"

    _rewrite_authorization(release, corrupt)
    report = verify_s2_authorizations(release)
    assert report["valid"] is False
    text = "\n".join(report["errors"])
    assert "wrong designated operator" in text
    assert "decision must be AUTHORIZE or WITHHOLD" in text
    assert "decision rationale is required" in text
    assert "candidate binding mismatch" in text
    assert "authorization boundary mismatch" in text


def test_authorization_digest_and_duplicate_id_corruption_are_detected(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    record_s2_authorization(release, decision="AUTHORIZE", decision_rationale="Valid.")
    original = _auth_path(release)
    copied = original.with_name("duplicate.json")
    shutil.copyfile(original, copied)
    report = verify_s2_authorizations(release)
    assert report["valid"] is False
    assert any("authorization IDs must be non-empty and unique" in error for error in report["errors"])

    copied.unlink()
    record = json.loads(original.read_text(encoding="utf-8"))
    record["decision_rationale"] = "tampered without rehash"
    _json(original, record)
    report = verify_s2_authorizations(release)
    assert any("authorization digest mismatch" in error for error in report["errors"])


def test_missing_supersession_target_and_cycle_are_detected(tmp_path) -> None:
    missing = _candidate(tmp_path / "missing")
    record_s2_authorization(missing, decision="AUTHORIZE", decision_rationale="Valid.")
    _rewrite_authorization(
        missing,
        lambda record: record.__setitem__("supersedes_authorization_id", "OBSAUTH-MISSING"),
    )
    report = verify_s2_authorizations(missing)
    assert any("superseded authorization is missing" in error for error in report["errors"])

    cycle = _candidate(tmp_path / "cycle")
    first = record_s2_authorization(cycle, decision="AUTHORIZE", decision_rationale="First.")["authorization"]
    second = record_s2_authorization(
        cycle,
        decision="WITHHOLD",
        decision_rationale="Second.",
        supersedes_authorization_id=first["authorization_id"],
    )["authorization"]
    first_path = cycle / "governance" / "authorizations" / f"{first['authorization_id']}.json"
    first_record = json.loads(first_path.read_text(encoding="utf-8"))
    first_record["supersedes_authorization_id"] = second["authorization_id"]
    first_record["authorization_sha256"] = publication_module._digest_record(
        first_record,
        "authorization_sha256",
    )
    _json(first_path, first_record)
    report = verify_s2_authorizations(cycle)
    assert any("supersession cycle detected" in error for error in report["errors"])


def test_authorization_cannot_be_superseded_twice(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    first = record_s2_authorization(release, decision="AUTHORIZE", decision_rationale="First.")["authorization"]
    second = record_s2_authorization(
        release,
        decision="WITHHOLD",
        decision_rationale="Second.",
        supersedes_authorization_id=first["authorization_id"],
    )["authorization"]
    second_path = release / "governance" / "authorizations" / f"{second['authorization_id']}.json"
    third = json.loads(second_path.read_text(encoding="utf-8"))
    third["authorization_id"] = "OBSAUTH-THIRD"
    third["authorization_sha256"] = publication_module._digest_record(third, "authorization_sha256")
    _json(second_path.with_name("OBSAUTH-THIRD.json"), third)
    report = verify_s2_authorizations(release)
    assert any("superseded more than once" in error for error in report["errors"])


def test_malformed_authorization_and_publication_files_fail_closed(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    auth_dir = release / "governance" / "authorizations"
    auth_dir.mkdir(parents=True, exist_ok=True)
    _json(auth_dir / "bad.json", [])
    report = verify_s2_authorizations(release)
    assert report["valid"] is False
    assert report["record_count"] == 0
    assert any("must be an object" in error for error in report["errors"])

    publication_path = release / "governance" / "publication.json"
    _json(publication_path, [])
    with pytest.raises(ObservatoryPublicationError, match="must be an object"):
        load_s2_publication(release)


def test_publication_semantic_corruption_is_detected(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    record_s2_authorization(release, decision="AUTHORIZE", decision_rationale="Authorize.")
    record_s2_publication(
        release,
        publication_evidence={"reference": "public-ref:test", "sha256": "8" * 64},
    )

    def corrupt(record) -> None:
        record["recorded_by"] = "other"
        record["candidate_reference"] = {"candidate_id": "OTHER"}
        record["authorization_reference"] = {"authorization_id": "OTHER", "authorization_sha256": "0" * 64}
        record["automatic_publication_performed"] = True
        record["boundary"] = "wrong"
        record["publication_evidence"] = {"reference": "invalid", "sha256": "bad"}

    _rewrite_publication(release, corrupt)
    report = verify_s2_publication_binding(release)
    assert report["valid"] is False
    text = "\n".join(report["errors"])
    assert "wrong publication operator" in text
    assert "publication candidate binding mismatch" in text
    assert "publication authorization binding mismatch" in text
    assert "automatic publication flag must remain false" in text
    assert "publication boundary mismatch" in text
    assert "publication evidence reference is invalid" in text
    assert "publication evidence sha256" in text


def test_publication_digest_and_missing_evidence_are_detected(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    record_s2_authorization(release, decision="AUTHORIZE", decision_rationale="Authorize.")
    record_s2_publication(
        release,
        publication_evidence={"reference": "public-ref:test", "sha256": "8" * 64},
    )
    path = release / "governance" / "publication.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["recorded_at"] = "tampered"
    _json(path, record)
    report = verify_s2_publication_binding(release)
    assert any("publication digest mismatch" in error for error in report["errors"])

    _rewrite_publication(release, lambda value: value.pop("publication_evidence", None))
    report = verify_s2_publication_binding(release)
    assert any("publication evidence is missing" in error for error in report["errors"])


def test_published_authorization_must_remain_active(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    first = record_s2_authorization(release, decision="AUTHORIZE", decision_rationale="Authorize.")["authorization"]
    record_s2_publication(
        release,
        publication_evidence={"reference": "public-ref:test", "sha256": "8" * 64},
    )
    first_path = release / "governance" / "authorizations" / f"{first['authorization_id']}.json"
    second = json.loads(first_path.read_text(encoding="utf-8"))
    second["authorization_id"] = "OBSAUTH-SUCCESSOR"
    second["decision"] = "WITHHOLD"
    second["decision_rationale"] = "Manual corruption after publication."
    second["supersedes_authorization_id"] = first["authorization_id"]
    second["authorization_sha256"] = publication_module._digest_record(second, "authorization_sha256")
    _json(first_path.with_name("OBSAUTH-SUCCESSOR.json"), second)
    report = verify_s2_authorizations(release)
    assert report["valid"] is False
    assert any("published authorization is no longer active" in error for error in report["errors"])
    binding = verify_s2_publication_binding(release)
    assert binding["valid"] is False
    assert any("active S2 authorization is not AUTHORIZE" in error for error in binding["errors"])


def test_authorization_postwrite_failure_rolls_back_file(tmp_path, monkeypatch) -> None:
    release = _candidate(tmp_path / "release")
    original = publication_module.verify_s2_authorizations
    calls = {"count": 0}

    def staged(path):
        calls["count"] += 1
        if calls["count"] == 1:
            return original(path)
        return {"valid": False, "errors": ["forced postwrite failure"]}

    monkeypatch.setattr(publication_module, "verify_s2_authorizations", staged)
    with pytest.raises(ObservatoryPublicationError, match="authorization failed verification"):
        record_s2_authorization(release, decision="AUTHORIZE", decision_rationale="Rollback test.")
    auth_dir = release / "governance" / "authorizations"
    assert auth_dir.is_dir()
    assert list(auth_dir.glob("*.json")) == []


def test_publication_postwrite_failure_rolls_back_file(tmp_path, monkeypatch) -> None:
    release = _candidate(tmp_path / "release")
    record_s2_authorization(release, decision="AUTHORIZE", decision_rationale="Authorize.")
    monkeypatch.setattr(
        publication_module,
        "verify_s2_publication_binding",
        lambda path: {"valid": False, "errors": ["forced postwrite failure"]},
    )
    with pytest.raises(ObservatoryPublicationError, match="publication failed verification"):
        record_s2_publication(
            release,
            publication_evidence={"reference": "public-ref:test", "sha256": "8" * 64},
        )
    assert not (release / "governance" / "publication.json").exists()


def test_load_helpers_return_empty_state_before_governance(tmp_path) -> None:
    release = _candidate(tmp_path / "release")
    assert load_s2_authorizations(release) == []
    assert load_s2_publication(release) is None
    assert verify_s2_authorizations(release) == {
        "valid": True,
        "errors": [],
        "record_count": 0,
        "active_count": 0,
    }
