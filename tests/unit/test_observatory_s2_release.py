from __future__ import annotations

import json

import pytest

from neuroai_workbench.observatory_s2_release import (
    OBJECT_FILES,
    ObservatoryS2ReleaseError,
    verify_observatory_v2_s2_candidate,
    write_observatory_v2_s2_candidate,
)
from neuroai_workbench.util import canonical_json_bytes, sha256_bytes


def _json(path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _gate_package(tmp_path):
    root = tmp_path / "gate"
    native = root / "native-candidate"
    native.mkdir(parents=True)
    records = {
        "entities.jsonl": '{"object_class":"Entity","entity_id":"ORG-1"}\n',
        "sources.jsonl": '{"object_class":"Source","source_id":"SRC-1"}\n',
        "events.jsonl": '{"object_class":"Event","event_id":"EV-1"}\n',
        "candidates.jsonl": '{"object_class":"Candidate","candidate_id":"CAND-1"}\n',
        "entity-predecessor-traces.jsonl": '{"trace":1}\n',
        "preserved-organizations.jsonl": '{"preserved":1}\n',
        "source-predecessor-traces.jsonl": '{"trace":2}\n',
        "predecessor-observation-evidence.jsonl": '{"observation":1}\n',
        "event-predecessor-traces.jsonl": '{"trace":3}\n',
        "candidate-predecessor-traces.jsonl": '{"trace":4}\n',
    }
    for filename, payload in records.items():
        (native / filename).write_text(payload, encoding="utf-8")
    native_manifest = {"manifest_sha256": "a" * 64}
    native_descriptor = {"release_authorized": False}
    _json(native / "manifest.json", native_manifest)
    _json(native / "descriptor.json", native_descriptor)
    for filename in (
        "v16-adjudication-state.json",
        "v17-successor-lineage.json",
        "residual-predecessor-state.json",
        "duplicate-container-proofs.json",
    ):
        _json(root / filename, {"state": filename})
    gate_descriptor = {
        "release_authorized": False,
        "representational_scope_complete": True,
        "workbench_compatibility_version": "0.3.0.dev0",
        "producer_workbench_commit": "1" * 40,
        "runtime_execution_pin": "2" * 40,
        "observatory_graph_schema_version": "1",
        "s2_predecessor_commit": "3" * 40,
    }
    gate_manifest = {"manifest_sha256": "b" * 64}
    _json(root / "descriptor.json", gate_descriptor)
    _json(root / "manifest.json", gate_manifest)
    return root


def test_s2_candidate_compiles_stable_object_surface(tmp_path, monkeypatch) -> None:
    gate = _gate_package(tmp_path)
    monkeypatch.setattr("neuroai_workbench.observatory_s2_release.verify_gate_a_package", lambda path: [])
    output = tmp_path / "s2"
    result = write_observatory_v2_s2_candidate(
        gate,
        output,
        release_tag="data-v0.3.0-observatory-v2-candidate",
        s2_predecessor_release_tag="data-v0.1.0-public-governing",
        field_proof_sha256="4" * 64,
    )

    assert result["descriptor"]["release_authorized"] is False
    assert result["descriptor"]["published"] is False
    assert result["descriptor"]["record_counts"] == {
        "Entity": 1,
        "Source": 1,
        "Observation": 0,
        "Assertion": 0,
        "Event": 1,
        "Relationship": 0,
        "Candidate": 1,
        "ReopeningDecision": 0,
    }
    for filename in OBJECT_FILES:
        assert (output / "records" / filename).is_file()
    assert (output / "migration" / "gate-a-descriptor.json").is_file()
    assert (output / "migration" / "gate-a-manifest.json").is_file()
    assert verify_observatory_v2_s2_candidate(output) == []


def test_s2_candidate_identity_is_content_derived_and_tamper_evident(tmp_path, monkeypatch) -> None:
    gate = _gate_package(tmp_path)
    monkeypatch.setattr("neuroai_workbench.observatory_s2_release.verify_gate_a_package", lambda path: [])
    output = tmp_path / "s2"
    result = write_observatory_v2_s2_candidate(
        gate,
        output,
        release_tag="data-v0.3.0-observatory-v2-candidate",
        s2_predecessor_release_tag="data-v0.1.0-public-governing",
        field_proof_sha256="4" * 64,
    )
    content = result["descriptor"]["candidate_content_sha256"]
    assert result["descriptor"]["candidate_id"] == f"OBS-V2-CAND-{content[:20].upper()}"

    with (output / "records" / "entities.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{"object_class":"Entity","entity_id":"ORG-TAMPER"}\n')
    errors = verify_observatory_v2_s2_candidate(output)
    assert any("file digest mismatch" in error for error in errors)
    assert any("content identity mismatch" in error for error in errors)


def test_s2_candidate_refuses_authorized_gate_package(tmp_path, monkeypatch) -> None:
    gate = _gate_package(tmp_path)
    descriptor = json.loads((gate / "descriptor.json").read_text(encoding="utf-8"))
    descriptor["release_authorized"] = True
    _json(gate / "descriptor.json", descriptor)
    monkeypatch.setattr("neuroai_workbench.observatory_s2_release.verify_gate_a_package", lambda path: [])
    with pytest.raises(ObservatoryS2ReleaseError, match="must remain unauthorized"):
        write_observatory_v2_s2_candidate(
            gate,
            tmp_path / "s2",
            release_tag="candidate",
            s2_predecessor_release_tag="predecessor",
            field_proof_sha256="4" * 64,
        )


def test_manifest_identity_binds_descriptor(tmp_path, monkeypatch) -> None:
    gate = _gate_package(tmp_path)
    monkeypatch.setattr("neuroai_workbench.observatory_s2_release.verify_gate_a_package", lambda path: [])
    output = tmp_path / "s2"
    write_observatory_v2_s2_candidate(
        gate,
        output,
        release_tag="candidate",
        s2_predecessor_release_tag="predecessor",
        field_proof_sha256="4" * 64,
    )
    descriptor = json.loads((output / "descriptor.json").read_text(encoding="utf-8"))
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["descriptor_sha256"] == sha256_bytes(canonical_json_bytes(descriptor))
    controlled = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    assert manifest["manifest_sha256"] == sha256_bytes(canonical_json_bytes(controlled))
