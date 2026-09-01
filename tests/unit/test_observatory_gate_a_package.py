from __future__ import annotations

import json

import pytest

import neuroai_workbench.observatory_gate_a_package as package_module
from neuroai_workbench.observatory_gate_a_package import (
    ObservatoryGateAPackageError,
    verify_gate_a_package,
    write_gate_a_migration_package,
)
from neuroai_workbench.util import atomic_write_json, canonical_json_bytes, sha256_bytes


def _checkpoint() -> dict:
    return {
        "mechanical_verification": "PASS",
        "representational_scope_complete": True,
        "gate_a_complete": False,
        "release_authorized": False,
        "candidate": {"placeholder": True},
        "v16_adjudication_state": {"state": "NONCANONICAL_CANDIDATE"},
        "v17_successor_lineage": {"state": "NONCANONICAL_CANDIDATE"},
        "residual_predecessor_state": {"state": "NONCANONICAL_CANDIDATE"},
        "duplicate_container_proofs": {"all_exact": True},
        "counts": {"native_objects": 403},
        "remaining_unresolved_families": [],
        "remaining_gate_requirements": ["HUMAN_REVIEW"],
    }


def _fake_candidate_writer(candidate, output_dir, **kwargs):
    output_dir.mkdir(parents=True, exist_ok=True)
    descriptor = {"candidate": candidate, "release_authorized": False}
    manifest = {
        "files": [],
        "descriptor_sha256": sha256_bytes(canonical_json_bytes(descriptor)),
        "release_authorized": False,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    atomic_write_json(output_dir / "descriptor.json", descriptor)
    atomic_write_json(output_dir / "manifest.json", manifest)
    return {"descriptor": descriptor, "manifest": manifest}


def _write(monkeypatch, tmp_path):
    monkeypatch.setattr(package_module, "verify_gate_a_migration_checkpoint", lambda checkpoint, delta16: {"valid": True, "errors": []})
    monkeypatch.setattr(package_module, "write_predecessor_migration_candidate_package", _fake_candidate_writer)
    return write_gate_a_migration_package(
        _checkpoint(),
        tmp_path,
        delta16={},
        v14_input_sha256="a" * 64,
        v16_input_sha256="b" * 64,
        delta16_input_sha256="c" * 64,
        v17_input_sha256="d" * 64,
        prima17_input_sha256="e" * 64,
        source_register14_input_sha256="f" * 64,
        monitor15_input_sha256="0" * 64,
        producer_workbench_commit="1" * 40,
        runtime_execution_pin="2" * 40,
        s2_predecessor_commit="3" * 40,
    )


def test_gate_a_package_is_deterministic_and_independently_verifiable(monkeypatch, tmp_path) -> None:
    first = _write(monkeypatch, tmp_path / "first")
    second = _write(monkeypatch, tmp_path / "second")
    assert first == second
    assert verify_gate_a_package(tmp_path / "first") == []
    assert first["descriptor"]["representational_scope_complete"] is True
    assert first["descriptor"]["gate_a_complete"] is False
    assert first["descriptor"]["release_authorized"] is False
    assert set(first["descriptor"]["inputs"]) == {
        "V14",
        "V16",
        "DELTA16",
        "V17",
        "PRIMA17",
        "SOURCE_REGISTER14",
        "MONITOR15",
    }


def test_gate_a_package_verifier_detects_root_state_tampering(monkeypatch, tmp_path) -> None:
    _write(monkeypatch, tmp_path)
    descriptor_path = tmp_path / "descriptor.json"
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    descriptor["representational_scope_complete"] = False
    atomic_write_json(descriptor_path, descriptor)
    errors = verify_gate_a_package(tmp_path)
    assert "Gate-A descriptor lost representational completeness state" in errors
    assert "Gate-A descriptor digest mismatch" in errors


def test_gate_a_package_verifier_detects_child_manifest_substitution(monkeypatch, tmp_path) -> None:
    _write(monkeypatch, tmp_path)
    child = tmp_path / "native-candidate" / "manifest.json"
    child_manifest = json.loads(child.read_text(encoding="utf-8"))
    child_manifest["release_authorized"] = True
    atomic_write_json(child, child_manifest)
    errors = verify_gate_a_package(tmp_path)
    assert "native-candidate manifest file digest mismatch" in errors


def test_gate_a_package_refuses_malformed_identity_or_false_representation(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(package_module, "verify_gate_a_migration_checkpoint", lambda checkpoint, delta16: {"valid": True, "errors": []})
    monkeypatch.setattr(package_module, "write_predecessor_migration_candidate_package", _fake_candidate_writer)
    checkpoint = _checkpoint()
    checkpoint["representational_scope_complete"] = False
    with pytest.raises(ObservatoryGateAPackageError, match="representationally complete"):
        write_gate_a_migration_package(
            checkpoint,
            tmp_path / "bad",
            delta16={},
            v14_input_sha256="a" * 64,
            v16_input_sha256="b" * 64,
            delta16_input_sha256="c" * 64,
            v17_input_sha256="d" * 64,
            prima17_input_sha256="e" * 64,
            source_register14_input_sha256="f" * 64,
            monitor15_input_sha256="0" * 64,
            producer_workbench_commit="1" * 40,
            runtime_execution_pin="2" * 40,
            s2_predecessor_commit="3" * 40,
        )
