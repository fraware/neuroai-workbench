from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

import neuroai_workbench.release_attestation as release_module
from neuroai_workbench.governance_opinions import REVIEW_TRACKS
from neuroai_workbench.release_attestation import (
    record_attested_publication,
    record_release_attestation,
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


def _assessments() -> list[dict[str, str]]:
    return [
        {"track": track, "state": "PASS", "rationale": f"TEST FIXTURE ONLY {track}."}
        for track in sorted(REVIEW_TRACKS)
    ]


def _workspace(tmp_path: Path, name: str = "workspace") -> Workspace:
    return Workspace.initialize(tmp_path / name)


def _attest(workspace: Workspace, candidate: dict[str, Any]) -> dict[str, Any]:
    return record_release_attestation(
        workspace,
        candidate=candidate,
        products=PRODUCTS,
        track_assessments=_assessments(),
        decision="AUTHORIZE",
        decision_rationale="TEST FIXTURE ONLY.",
        actor="fraware",
    )["attestation"]


def _with_hash(record: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(record)
    updated["attestation_sha256"] = release_module._hash(updated, "attestation_sha256")
    return updated


def _attestation_events(records: list[dict[str, Any]]) -> Counter[tuple[str, str]]:
    return Counter((str(item["attestation_id"]), str(item["attestation_sha256"])) for item in records)


def _patch_attestation_store(
    monkeypatch: pytest.MonkeyPatch,
    records: list[dict[str, Any]],
    *,
    publications: list[dict[str, Any]] | None = None,
) -> None:
    monkeypatch.setattr(release_module, "load_release_attestations", lambda workspace: records)
    monkeypatch.setattr(release_module, "load_attested_publications", lambda workspace: publications or [])
    events = _attestation_events(records)
    monkeypatch.setattr(
        release_module,
        "_events",
        lambda workspace, action: events if action == release_module.ATTESTATION_EVENT else Counter(),
    )


def test_attestation_verifier_reports_event_chain_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    monkeypatch.setattr(
        release_module,
        "_events",
        lambda workspace, action: (_ for _ in ()).throw(ValueError("bad chain")),
    )
    report = verify_release_attestations(workspace)
    assert report["valid"] is False
    assert "bad chain" in report["errors"]


def test_attestation_semantic_verifier_handles_invalid_normalized_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    record = _attest(workspace, _candidate("v1.8-semantic-invalid"))
    record["products"] = "invalid"
    record = _with_hash(record)
    _patch_attestation_store(monkeypatch, [record])
    report = verify_release_attestations(workspace)
    assert report["valid"] is False
    assert any("At least one product" in error for error in report["errors"])


def test_attestation_verifier_detects_missing_and_cross_object_supersession(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    first = _attest(workspace, _candidate("v1.8-supersession-verifier"))

    missing = deepcopy(first)
    missing["attestation_id"] = "RELATT-MISSINGTARGET"
    missing["supersedes_attestation_id"] = "RELATT-NOTFOUND"
    missing = _with_hash(missing)
    _patch_attestation_store(monkeypatch, [missing])
    report = verify_release_attestations(workspace)
    assert any("supersession target missing" in error for error in report["errors"])

    second = deepcopy(first)
    second["attestation_id"] = "RELATT-CROSSOBJECT"
    second["supersedes_attestation_id"] = first["attestation_id"]
    second["candidate_reference"] = dict(second["candidate_reference"])
    second["candidate_reference"]["candidate_serialized_sha256"] = "c" * 64
    second = _with_hash(second)
    _patch_attestation_store(monkeypatch, [first, second])
    report = verify_release_attestations(workspace)
    assert any("supersession changes the exact candidate representation" in error for error in report["errors"])


def test_attestation_verifier_detects_published_double_and_cyclic_supersession(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    first = _attest(workspace, _candidate("v1.8-supersession-shapes"))

    second = deepcopy(first)
    second["attestation_id"] = "RELATT-SECOND"
    second["supersedes_attestation_id"] = first["attestation_id"]
    second = _with_hash(second)
    publication_ref = {"attestation_reference": {"attestation_id": first["attestation_id"]}}
    _patch_attestation_store(monkeypatch, [first, second], publications=[publication_ref])
    report = verify_release_attestations(workspace)
    assert any("published attestation cannot be superseded" in error for error in report["errors"])

    third = deepcopy(first)
    third["attestation_id"] = "RELATT-THIRD"
    third["supersedes_attestation_id"] = first["attestation_id"]
    third = _with_hash(third)
    _patch_attestation_store(monkeypatch, [first, second, third])
    report = verify_release_attestations(workspace)
    assert "An attestation is superseded more than once" in report["errors"]

    cycle_a = deepcopy(first)
    cycle_a["attestation_id"] = "RELATT-CYCLEA"
    cycle_a["supersedes_attestation_id"] = "RELATT-CYCLEB"
    cycle_a = _with_hash(cycle_a)
    cycle_b = deepcopy(first)
    cycle_b["attestation_id"] = "RELATT-CYCLEB"
    cycle_b["supersedes_attestation_id"] = "RELATT-CYCLEA"
    cycle_b = _with_hash(cycle_b)
    _patch_attestation_store(monkeypatch, [cycle_a, cycle_b])
    report = verify_release_attestations(workspace)
    assert "Attestation supersession cycle detected" in report["errors"]


def test_attestation_verifier_detects_multiple_active_attestations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    first = _attest(workspace, _candidate("v1.8-multiple-active"))
    second = deepcopy(first)
    second["attestation_id"] = "RELATT-ACTIVESECOND"
    second = _with_hash(second)
    _patch_attestation_store(monkeypatch, [first, second])
    report = verify_release_attestations(workspace)
    assert "One exact candidate representation has multiple active attestations" in report["errors"]


def test_recorder_defensive_candidate_shape_guards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    monkeypatch.setattr(release_module, "validate_successor_candidate", lambda candidate: {"valid": True})

    with pytest.raises(ValueError, match="metadata and predecessor"):
        record_release_attestation(
            workspace,
            candidate={"metadata": [], "predecessor_reference": {}, "withheld_claims": ["x"]},
            products=PRODUCTS,
            track_assessments=_assessments(),
            decision="WITHHOLD",
            decision_rationale="TEST FIXTURE ONLY.",
            actor="fraware",
        )

    with pytest.raises(ValueError, match="withheld claims"):
        record_release_attestation(
            workspace,
            candidate={
                "metadata": {"candidate_id": "candidate", "canonical_sha256": "a" * 64},
                "predecessor_reference": {"release_version": "v1", "sha256": "b" * 64},
                "withheld_claims": [],
            },
            products=PRODUCTS,
            track_assessments=_assessments(),
            decision="WITHHOLD",
            decision_rationale="TEST FIXTURE ONLY.",
            actor="fraware",
        )

    with pytest.raises(ValueError, match="identifiers are required"):
        record_release_attestation(
            workspace,
            candidate={
                "metadata": {"candidate_id": "", "canonical_sha256": "a" * 64},
                "predecessor_reference": {"release_version": "v1", "sha256": "b" * 64},
                "withheld_claims": ["x"],
            },
            products=PRODUCTS,
            track_assessments=_assessments(),
            decision="WITHHOLD",
            decision_rationale="TEST FIXTURE ONLY.",
            actor="fraware",
        )


def test_recorder_fails_closed_on_internal_schema_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    candidate = _candidate("v1.8-schema-defence")
    original = release_module._schema_errors

    def injected(value: dict[str, Any], schema_name: str) -> list[str]:
        if schema_name == release_module.ATTESTATION_SCHEMA and "attestation_id" in value:
            return ["injected schema failure"]
        return original(value, schema_name)

    monkeypatch.setattr(release_module, "_schema_errors", injected)
    with pytest.raises(ValueError, match="failed validation"):
        _attest(workspace, candidate)


def _publication_context(tmp_path: Path) -> tuple[Workspace, dict[str, Any], dict[str, Any]]:
    workspace = _workspace(tmp_path, "publication")
    attestation = _attest(workspace, _candidate("v1.8-publication-verifier"))
    publication = record_attested_publication(
        workspace,
        attestation_id=attestation["attestation_id"],
        publication_evidence={"reference": "public-ref:test/release", "sha256": "b" * 64},
        actor="fraware",
    )["publication"]
    return workspace, attestation, publication


def _patch_publication_store(
    monkeypatch: pytest.MonkeyPatch,
    attestation: dict[str, Any],
    publications: list[dict[str, Any]],
    *,
    include_events: bool = True,
) -> None:
    monkeypatch.setattr(release_module, "verify_release_attestations", lambda workspace: {"valid": True})
    monkeypatch.setattr(release_module, "load_release_attestations", lambda workspace: [attestation])
    monkeypatch.setattr(release_module, "load_attested_publications", lambda workspace: publications)
    events = (
        Counter((str(item["publication_id"]), str(item["publication_sha256"])) for item in publications)
        if include_events
        else Counter()
    )
    monkeypatch.setattr(release_module, "_events", lambda workspace, action: events)


def test_publication_verifier_reports_event_chain_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    monkeypatch.setattr(release_module, "verify_release_attestations", lambda workspace: {"valid": True})
    monkeypatch.setattr(
        release_module,
        "_events",
        lambda workspace, action: (_ for _ in ()).throw(ValueError("bad publication chain")),
    )
    report = verify_attested_publications(workspace)
    assert report["valid"] is False
    assert "bad publication chain" in report["errors"]


def test_publication_verifier_recomputes_authority_binding_and_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, attestation, publication = _publication_context(tmp_path)

    wrong_actor = deepcopy(publication)
    wrong_actor["recorded_by"] = "other"
    wrong_actor["publication_sha256"] = release_module._hash(wrong_actor, "publication_sha256")
    _patch_publication_store(monkeypatch, attestation, [wrong_actor])
    report = verify_attested_publications(workspace)
    assert any("wrong designated authority" in error for error in report["errors"])

    wrong_binding = deepcopy(publication)
    wrong_binding["attestation_reference"] = dict(wrong_binding["attestation_reference"])
    wrong_binding["attestation_reference"]["attestation_sha256"] = "c" * 64
    wrong_binding["publication_sha256"] = release_module._hash(wrong_binding, "publication_sha256")
    _patch_publication_store(monkeypatch, attestation, [wrong_binding])
    report = verify_attested_publications(workspace)
    assert any("active authorization binding mismatch" in error for error in report["errors"])

    invalid_evidence = deepcopy(publication)
    invalid_evidence["publication_evidence"] = "invalid"
    invalid_evidence["publication_sha256"] = release_module._hash(invalid_evidence, "publication_sha256")
    _patch_publication_store(monkeypatch, attestation, [invalid_evidence])
    report = verify_attested_publications(workspace)
    assert any("publication evidence is invalid" in error for error in report["errors"])

    bad_reference = deepcopy(publication)
    bad_reference["publication_evidence"] = {"reference": "bad", "sha256": "b" * 64}
    bad_reference["publication_sha256"] = release_module._hash(bad_reference, "publication_sha256")
    _patch_publication_store(monkeypatch, attestation, [bad_reference])
    report = verify_attested_publications(workspace)
    assert any("evidence reference is invalid" in error for error in report["errors"])

    bad_digest = deepcopy(publication)
    bad_digest["publication_evidence"] = {"reference": "public-ref:test/release", "sha256": "bad"}
    bad_digest["publication_sha256"] = release_module._hash(bad_digest, "publication_sha256")
    _patch_publication_store(monkeypatch, attestation, [bad_digest])
    report = verify_attested_publications(workspace)
    assert any("lowercase SHA-256" in error for error in report["errors"])


def test_publication_verifier_detects_missing_and_duplicate_witnesses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, attestation, publication = _publication_context(tmp_path)
    _patch_publication_store(monkeypatch, attestation, [publication], include_events=False)
    report = verify_attested_publications(workspace)
    assert any("event missing or duplicated" in error for error in report["errors"])

    duplicate_id = deepcopy(publication)
    duplicate_id["publication_sha256"] = release_module._hash(duplicate_id, "publication_sha256")
    _patch_publication_store(monkeypatch, attestation, [publication, duplicate_id])
    report = verify_attested_publications(workspace)
    assert "Duplicate publication_id" in report["errors"]
    assert "An attestation has multiple publication records" in report["errors"]


def test_publication_recorder_fails_closed_on_internal_schema_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    attestation = _attest(workspace, _candidate("v1.8-publication-schema-defence"))
    original = release_module._schema_errors

    def injected(value: dict[str, Any], schema_name: str) -> list[str]:
        if schema_name == release_module.PUBLICATION_SCHEMA and "publication_id" in value:
            return ["injected schema failure"]
        return original(value, schema_name)

    monkeypatch.setattr(release_module, "_schema_errors", injected)
    with pytest.raises(ValueError, match="failed schema validation"):
        record_attested_publication(
            workspace,
            attestation_id=attestation["attestation_id"],
            publication_evidence={"reference": "public-ref:test/release", "sha256": "b" * 64},
            actor="fraware",
        )
