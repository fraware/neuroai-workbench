#!/usr/bin/env python3
"""Execute the complete noncanonical Observatory-v2 Gate-A migration run.

This operator command binds the exact frozen predecessor bytes, executes the corrected
field-preservation proof, builds the representationally complete migration checkpoint,
validates the native graph using class-qualified references and precision-safe temporal
semantics, writes/verifies the identity-bound package, and emits the pending human-review
packet. It never authorizes publication or self-completes human review.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from neuroai_workbench.observatory_gate_a_migration import build_gate_a_migration_checkpoint
from neuroai_workbench.observatory_gate_a_package import (
    verify_gate_a_package,
    write_gate_a_migration_package,
)
from neuroai_workbench.observatory_gate_a_review import build_gate_a_review_packet
from neuroai_workbench.observatory_gate_a_validation import validate_gate_a_native_graph
from neuroai_workbench.util import atomic_write_json, sha256_bytes

FROZEN_INPUT_SHA256 = {
    "V14": "00985fa168b26c4e02df485895d728ee30191aea436b4e3956c60657e2ffc3be",
    "V16": "937b2fcd807392e64f946f88a89756cc91890cc6db9f98e519035725e46c7035",
    "DELTA16": "49ef4944e4dd7e5d4b3534926e41220a1493ef12d68965a7b6caa4431524b0c5",
    "V17": "9cc36aacb4c791c9830990b58e144f223925f3ad492016abaea44727b48a0b70",
    "PRIMA17": "f2966b60c3c58bb11bfdd80324e152f6ff3faaf1f632d287e51cdfdccbcde09c",
    "SOURCE_REGISTER14": "36dce4ca9f13f8046fca31bfbeabb5c01903eb077594a37aee63749612d2a1a5",
    "MONITOR15": "1d1f9774a3ad559792fa2bc7e459a4a65c6574ec14fa0b1501240bbb18dcc315",
}


class GateARunError(RuntimeError):
    """Raised when the operator run cannot establish an exact mechanical checkpoint."""


def _require_hex(value: str, *, length: int, field: str) -> str:
    if len(value) != length or any(char not in "0123456789abcdef" for char in value):
        raise GateARunError(f"{field} must be lowercase {length}-character hexadecimal")
    return value


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateARunError(f"Cannot read JSON input {path}: {exc}") from exc


def _bind_frozen_input(role: str, path: Path) -> dict[str, Any]:
    if role not in FROZEN_INPUT_SHA256:
        raise GateARunError(f"Unknown frozen input role {role}")
    if not path.is_file():
        raise GateARunError(f"Frozen input does not exist: {path}")
    raw = path.read_bytes()
    observed = sha256_bytes(raw)
    expected = FROZEN_INPUT_SHA256[role]
    if observed != expected:
        raise GateARunError(
            f"Frozen input hash mismatch for {role}: expected {expected}, observed {observed}"
        )
    return {
        "role": role,
        "path": str(path),
        "filename": path.name,
        "size_bytes": len(raw),
        "sha256": observed,
    }


def _load_field_proof_module() -> ModuleType:
    script = Path(__file__).resolve().with_name("observatory_v2_migration_proof.py")
    spec = importlib.util.spec_from_file_location("observatory_v2_migration_proof_gate_a", script)
    if spec is None or spec.loader is None:
        raise GateARunError(f"Cannot load field-proof implementation from {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def execute_gate_a_run(
    *,
    paths: dict[str, Path],
    output_dir: Path,
    producer_workbench_commit: str,
    runtime_execution_pin: str,
    s2_predecessor_commit: str,
    observatory_graph_schema_version: str = "1",
) -> dict[str, Any]:
    """Execute the exact mechanical Gate-A workflow and return its execution report."""
    if set(paths) != set(FROZEN_INPUT_SHA256):
        missing = sorted(set(FROZEN_INPUT_SHA256) - set(paths))
        extra = sorted(set(paths) - set(FROZEN_INPUT_SHA256))
        raise GateARunError(f"Frozen input role mismatch: missing={missing}, extra={extra}")
    producer = _require_hex(producer_workbench_commit, length=40, field="producer_workbench_commit")
    runtime_pin = _require_hex(runtime_execution_pin, length=40, field="runtime_execution_pin")
    s2_commit = _require_hex(s2_predecessor_commit, length=40, field="s2_predecessor_commit")
    if not observatory_graph_schema_version.strip():
        raise GateARunError("observatory_graph_schema_version must be non-empty")

    input_manifest = [
        _bind_frozen_input(role, paths[role])
        for role in sorted(FROZEN_INPUT_SHA256)
    ]
    loaded = {role: _load_json(paths[role]) for role in FROZEN_INPUT_SHA256}
    for role in ("V14", "V16", "DELTA16", "V17", "PRIMA17"):
        if not isinstance(loaded[role], dict):
            raise GateARunError(f"{role} must be a JSON object")
    for role in ("SOURCE_REGISTER14", "MONITOR15"):
        if not isinstance(loaded[role], list):
            raise GateARunError(f"{role} must be a JSON array")

    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_dir / "frozen-input-manifest.json", input_manifest)

    field_proof_module = _load_field_proof_module()
    field_proof_inputs = [
        ("V14", paths["V14"]),
        ("V16", paths["V16"]),
        ("DELTA16", paths["DELTA16"]),
        ("V17", paths["V17"]),
        ("MONITOR15", paths["MONITOR15"]),
    ]
    field_proof = field_proof_module.build_proof(field_proof_inputs)
    field_proof_dir = output_dir / "field-proof"
    field_proof_module.write_proof(field_proof, field_proof_dir)
    if field_proof.get("field_preservation") != "PASS":
        raise GateARunError("Corrected field-preservation proof did not PASS")

    checkpoint = build_gate_a_migration_checkpoint(
        v14_release=loaded["V14"],
        v16_refresh=loaded["V16"],
        delta16=loaded["DELTA16"],
        v17_successor=loaded["V17"],
        prima17=loaded["PRIMA17"],
        source_register14=loaded["SOURCE_REGISTER14"],
        monitor15=loaded["MONITOR15"],
    )
    if checkpoint.get("mechanical_verification") != "PASS":
        raise GateARunError(f"Gate-A checkpoint failed: {checkpoint.get('verification_errors')}")
    if checkpoint.get("representational_scope_complete") is not True:
        raise GateARunError("Gate-A predecessor scope is not representationally complete")
    atomic_write_json(output_dir / "gate-a-checkpoint.json", checkpoint)

    native_validation = validate_gate_a_native_graph(
        checkpoint,
        delta16=loaded["DELTA16"],
    )
    atomic_write_json(output_dir / "native-graph-validation.json", native_validation)
    if native_validation.get("valid") is not True:
        raise GateARunError(f"Native graph validation failed: {native_validation.get('errors')}")

    package_dir = output_dir / "gate-a-package"
    package = write_gate_a_migration_package(
        checkpoint,
        package_dir,
        delta16=loaded["DELTA16"],
        v14_input_sha256=FROZEN_INPUT_SHA256["V14"],
        v16_input_sha256=FROZEN_INPUT_SHA256["V16"],
        delta16_input_sha256=FROZEN_INPUT_SHA256["DELTA16"],
        v17_input_sha256=FROZEN_INPUT_SHA256["V17"],
        prima17_input_sha256=FROZEN_INPUT_SHA256["PRIMA17"],
        source_register14_input_sha256=FROZEN_INPUT_SHA256["SOURCE_REGISTER14"],
        monitor15_input_sha256=FROZEN_INPUT_SHA256["MONITOR15"],
        producer_workbench_commit=producer,
        runtime_execution_pin=runtime_pin,
        s2_predecessor_commit=s2_commit,
        observatory_graph_schema_version=observatory_graph_schema_version,
    )
    package_errors = verify_gate_a_package(package_dir)
    atomic_write_json(output_dir / "gate-a-package-verification.json", {"valid": not package_errors, "errors": package_errors})
    if package_errors:
        raise GateARunError(f"Gate-A package verification failed: {package_errors}")

    review_packet = build_gate_a_review_packet(
        checkpoint=checkpoint,
        v14_release=loaded["V14"],
        v16_refresh=loaded["V16"],
        delta16=loaded["DELTA16"],
        v17_successor=loaded["V17"],
        prima17=loaded["PRIMA17"],
        source_register14=loaded["SOURCE_REGISTER14"],
        monitor15=loaded["MONITOR15"],
    )
    atomic_write_json(output_dir / "human-review-packet.json", review_packet)

    report = {
        "schema_version": "1",
        "execution_type": "OBSERVATORY_V2_GATE_A_MECHANICAL_RUN",
        "state": "MECHANICAL_GATES_PASSED_HUMAN_REVIEW_PENDING",
        "release_authorized": False,
        "gate_a_complete": False,
        "representational_scope_complete": True,
        "native_v2_materialization_complete": False,
        "input_manifest": input_manifest,
        "field_preservation": field_proof["field_preservation"],
        "field_proof_sha256": field_proof["proof_sha256"],
        "field_reconciliation": field_proof["reconciliation"],
        "native_graph_validation": {
            "valid": True,
            "object_count": native_validation["object_count"],
            "class_counts": native_validation["class_counts"],
            "typed_reference_checks": native_validation["typed_reference_checks"],
            "temporal_values_checked": native_validation["temporal_values_checked"],
            "cross_class_id_collisions": native_validation["cross_class_id_collisions"],
        },
        "gate_a_package_manifest_sha256": package["manifest"]["manifest_sha256"],
        "gate_a_package_descriptor_sha256": package["manifest"]["descriptor_sha256"],
        "human_review_packet_sha256": review_packet["review_packet_sha256"],
        "human_review_state": "PENDING_HUMAN_REVIEW",
        "producer_workbench_commit": producer,
        "runtime_execution_pin": runtime_pin,
        "s2_predecessor_commit": s2_commit,
        "observatory_graph_schema_version": observatory_graph_schema_version,
        "remaining_gate_requirements": ["REPRESENTATIVE_HUMAN_DOMAIN_REVIEW"],
    }
    atomic_write_json(output_dir / "execution-report.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v14", required=True, type=Path)
    parser.add_argument("--v16", required=True, type=Path)
    parser.add_argument("--delta16", required=True, type=Path)
    parser.add_argument("--v17", required=True, type=Path)
    parser.add_argument("--prima17", required=True, type=Path)
    parser.add_argument("--source-register14", required=True, type=Path)
    parser.add_argument("--monitor15", required=True, type=Path)
    parser.add_argument("--producer-workbench-commit", required=True)
    parser.add_argument("--runtime-execution-pin", required=True)
    parser.add_argument("--s2-predecessor-commit", required=True)
    parser.add_argument("--observatory-graph-schema-version", default="1")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = execute_gate_a_run(
        paths={
            "V14": args.v14,
            "V16": args.v16,
            "DELTA16": args.delta16,
            "V17": args.v17,
            "PRIMA17": args.prima17,
            "SOURCE_REGISTER14": args.source_register14,
            "MONITOR15": args.monitor15,
        },
        output_dir=args.output,
        producer_workbench_commit=args.producer_workbench_commit,
        runtime_execution_pin=args.runtime_execution_pin,
        s2_predecessor_commit=args.s2_predecessor_commit,
        observatory_graph_schema_version=args.observatory_graph_schema_version,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
