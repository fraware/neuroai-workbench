from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from neuroai_workbench.util import sha256_bytes


def _module() -> ModuleType:
    script = Path(__file__).resolve().parents[2] / "scripts" / "observatory_v2_gate_a_run.py"
    spec = importlib.util.spec_from_file_location("observatory_v2_gate_a_run_test", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _inputs(tmp_path: Path) -> tuple[dict[str, Path], dict[str, str]]:
    values = {
        "V14": {"v": 14},
        "V16": {"v": 16},
        "DELTA16": {"d": 16},
        "V17": {"v": 17},
        "PRIMA17": {"p": 17},
        "SOURCE_REGISTER14": [{"source_id": "SRC-1"}],
        "MONITOR15": [{"monitor_id": "MON-1"}],
    }
    paths: dict[str, Path] = {}
    hashes: dict[str, str] = {}
    for role, value in values.items():
        path = tmp_path / f"{role}.json"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        paths[role] = path
        hashes[role] = sha256_bytes(path.read_bytes())
    return paths, hashes


def _patch_success(mod: ModuleType, monkeypatch) -> None:
    class FieldProof:
        @staticmethod
        def build_proof(inputs):
            assert inputs
            return {
                "field_preservation": "PASS",
                "proof_sha256": "a" * 64,
                "reconciliation": {"invented_value_count": 0},
            }

        @staticmethod
        def write_proof(proof, output):
            output.mkdir(parents=True, exist_ok=True)
            (output / "migration-proof.json").write_text(json.dumps(proof), encoding="utf-8")

    monkeypatch.setattr(mod, "_load_field_proof_module", lambda: FieldProof)
    monkeypatch.setattr(
        mod,
        "build_gate_a_migration_checkpoint",
        lambda **kwargs: {
            "mechanical_verification": "PASS",
            "representational_scope_complete": True,
            "release_authorized": False,
            "gate_a_complete": False,
        },
    )
    monkeypatch.setattr(
        mod,
        "validate_gate_a_native_graph",
        lambda checkpoint, delta16: {
            "valid": True,
            "object_count": 403,
            "class_counts": {"Candidate": 9, "Entity": 153, "Event": 5, "Source": 236},
            "typed_reference_checks": 100,
            "temporal_values_checked": 15,
            "cross_class_id_collisions": {},
            "errors": [],
        },
    )

    def write_package(checkpoint, output_dir, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        return {"manifest": {"manifest_sha256": "b" * 64, "descriptor_sha256": "c" * 64}}

    monkeypatch.setattr(mod, "write_gate_a_migration_package", write_package)
    monkeypatch.setattr(mod, "verify_gate_a_package", lambda output_dir: [])
    monkeypatch.setattr(
        mod,
        "build_gate_a_review_packet",
        lambda **kwargs: {
            "state": "PENDING_HUMAN_REVIEW",
            "review_packet_sha256": "d" * 64,
        },
    )


def test_gate_a_run_binds_inputs_and_reduces_remaining_gate_to_human_review(tmp_path, monkeypatch) -> None:
    mod = _module()
    paths, hashes = _inputs(tmp_path / "inputs")
    monkeypatch.setattr(mod, "FROZEN_INPUT_SHA256", hashes)
    _patch_success(mod, monkeypatch)

    output = tmp_path / "out"
    report = mod.execute_gate_a_run(
        paths=paths,
        output_dir=output,
        producer_workbench_commit="1" * 40,
        runtime_execution_pin="2" * 40,
        s2_predecessor_commit="3" * 40,
    )

    assert report["state"] == "MECHANICAL_GATES_PASSED_HUMAN_REVIEW_PENDING"
    assert report["release_authorized"] is False
    assert report["gate_a_complete"] is False
    assert report["representational_scope_complete"] is True
    assert report["field_proof_sha256"] == "a" * 64
    assert report["native_graph_validation"]["object_count"] == 403
    assert report["gate_a_package_manifest_sha256"] == "b" * 64
    assert report["human_review_packet_sha256"] == "d" * 64
    assert report["remaining_gate_requirements"] == ["REPRESENTATIVE_HUMAN_DOMAIN_REVIEW"]
    assert (output / "frozen-input-manifest.json").is_file()
    assert (output / "field-proof" / "migration-proof.json").is_file()
    assert (output / "gate-a-checkpoint.json").is_file()
    assert (output / "native-graph-validation.json").is_file()
    assert (output / "human-review-packet.json").is_file()
    assert (output / "execution-report.json").is_file()


def test_gate_a_run_rejects_any_frozen_input_byte_substitution(tmp_path, monkeypatch) -> None:
    mod = _module()
    paths, hashes = _inputs(tmp_path / "inputs")
    monkeypatch.setattr(mod, "FROZEN_INPUT_SHA256", hashes)
    paths["V14"].write_text(json.dumps({"v": "substituted"}), encoding="utf-8")

    with pytest.raises(mod.GateARunError, match="Frozen input hash mismatch for V14"):
        mod.execute_gate_a_run(
            paths=paths,
            output_dir=tmp_path / "out",
            producer_workbench_commit="1" * 40,
            runtime_execution_pin="2" * 40,
            s2_predecessor_commit="3" * 40,
        )


def test_gate_a_run_fails_before_package_when_native_graph_validation_fails(tmp_path, monkeypatch) -> None:
    mod = _module()
    paths, hashes = _inputs(tmp_path / "inputs")
    monkeypatch.setattr(mod, "FROZEN_INPUT_SHA256", hashes)
    _patch_success(mod, monkeypatch)
    monkeypatch.setattr(
        mod,
        "validate_gate_a_native_graph",
        lambda checkpoint, delta16: {
            "valid": False,
            "errors": ["Event:EV-1.source_ids references missing Source 'COLLIDE'"],
        },
    )

    with pytest.raises(mod.GateARunError, match="Native graph validation failed"):
        mod.execute_gate_a_run(
            paths=paths,
            output_dir=tmp_path / "out",
            producer_workbench_commit="1" * 40,
            runtime_execution_pin="2" * 40,
            s2_predecessor_commit="3" * 40,
        )
