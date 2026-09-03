"""Deterministic identity-bound packaging for the full Gate-A migration checkpoint."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import __version__
from .observatory_gate_a_migration import (
    GATE_A_MIGRATION_BOUNDARY,
    verify_gate_a_migration_checkpoint,
)
from .observatory_migration_candidate import write_predecessor_migration_candidate_package
from .util import atomic_write_json, canonical_json_bytes, sha256_bytes

GATE_A_PACKAGE_BOUNDARY = (
    "Deterministic noncanonical Gate-A migration package. The package binds exact frozen predecessor inputs, "
    "Workbench producer/runtime identity, graph schema generation, S2 predecessor commit, the native candidate, "
    "and all governed preservation surfaces. Package integrity does not confer publication authority."
)


class ObservatoryGateAPackageError(ValueError):
    """Raised when a Gate-A package cannot be bound deterministically."""


def _require_hex(value: Any, *, length: int, field: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(char not in "0123456789abcdef" for char in value):
        raise ObservatoryGateAPackageError(f"{field} must be a lowercase {length}-character hexadecimal identity")
    return value


def _canonical_json_file(path: Path, value: Any) -> str:
    atomic_write_json(path, value)
    return sha256_bytes(path.read_bytes())


def write_gate_a_migration_package(
    checkpoint: dict[str, Any],
    output_dir: Path,
    *,
    delta16: dict[str, Any],
    v14_input_sha256: str,
    v16_input_sha256: str,
    delta16_input_sha256: str,
    v17_input_sha256: str,
    prima17_input_sha256: str,
    source_register14_input_sha256: str,
    monitor15_input_sha256: str,
    producer_workbench_commit: str,
    runtime_execution_pin: str,
    s2_predecessor_commit: str,
    observatory_graph_schema_version: str = "1",
) -> dict[str, Any]:
    """Write one hierarchical package binding every current Gate-A migration surface."""
    report = verify_gate_a_migration_checkpoint(checkpoint, delta16=delta16)
    if not report["valid"]:
        raise ObservatoryGateAPackageError(f"cannot package invalid Gate-A checkpoint: {report['errors']}")
    if checkpoint.get("mechanical_verification") != "PASS":
        raise ObservatoryGateAPackageError("Gate-A checkpoint must have mechanical PASS before packaging")
    if checkpoint.get("representational_scope_complete") is not True:
        raise ObservatoryGateAPackageError("Gate-A package requires representationally complete predecessor scope")
    if checkpoint.get("gate_a_complete") is not False or checkpoint.get("release_authorized") is not False:
        raise ObservatoryGateAPackageError("Gate-A package must remain incomplete and unauthorized")

    inputs = {
        "V14": _require_hex(v14_input_sha256, length=64, field="v14_input_sha256"),
        "V16": _require_hex(v16_input_sha256, length=64, field="v16_input_sha256"),
        "DELTA16": _require_hex(delta16_input_sha256, length=64, field="delta16_input_sha256"),
        "V17": _require_hex(v17_input_sha256, length=64, field="v17_input_sha256"),
        "PRIMA17": _require_hex(prima17_input_sha256, length=64, field="prima17_input_sha256"),
        "SOURCE_REGISTER14": _require_hex(
            source_register14_input_sha256,
            length=64,
            field="source_register14_input_sha256",
        ),
        "MONITOR15": _require_hex(monitor15_input_sha256, length=64, field="monitor15_input_sha256"),
    }
    producer = _require_hex(producer_workbench_commit, length=40, field="producer_workbench_commit")
    runtime_pin = _require_hex(runtime_execution_pin, length=40, field="runtime_execution_pin")
    s2_commit = _require_hex(s2_predecessor_commit, length=40, field="s2_predecessor_commit")
    if not isinstance(observatory_graph_schema_version, str) or not observatory_graph_schema_version.strip():
        raise ObservatoryGateAPackageError("observatory_graph_schema_version must be non-empty")

    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_dir = output_dir / "native-candidate"
    candidate_package = write_predecessor_migration_candidate_package(
        checkpoint["candidate"],
        candidate_dir,
        v14_input_sha256=inputs["V14"],
        v16_input_sha256=inputs["V16"],
        producer_commit=producer,
        runtime_execution_pin=runtime_pin,
        s2_predecessor_commit=s2_commit,
        observatory_graph_schema_version=observatory_graph_schema_version,
    )

    state_files = {
        "v16-adjudication-state.json": checkpoint["v16_adjudication_state"],
        "v17-successor-lineage.json": checkpoint["v17_successor_lineage"],
        "residual-predecessor-state.json": checkpoint["residual_predecessor_state"],
        "duplicate-container-proofs.json": checkpoint["duplicate_container_proofs"],
    }
    state_digests: dict[str, str] = {}
    for filename, value in sorted(state_files.items()):
        state_digests[filename] = _canonical_json_file(output_dir / filename, value)

    candidate_manifest_bytes = (candidate_dir / "manifest.json").read_bytes()
    candidate_descriptor_bytes = (candidate_dir / "descriptor.json").read_bytes()
    descriptor = {
        "schema_version": "1",
        "package_type": "OBSERVATORY_V2_GATE_A_MIGRATION_CHECKPOINT",
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "gate_a_complete": False,
        "representational_scope_complete": True,
        "native_v2_materialization_complete": False,
        "counts": checkpoint["counts"],
        "remaining_unresolved_families": checkpoint["remaining_unresolved_families"],
        "remaining_gate_requirements": checkpoint["remaining_gate_requirements"],
        "workbench_compatibility_version": __version__,
        "producer_workbench_commit": producer,
        "runtime_execution_pin": runtime_pin,
        "observatory_graph_schema_version": observatory_graph_schema_version,
        "s2_predecessor_commit": s2_commit,
        "inputs": inputs,
        "native_candidate_manifest_sha256": sha256_bytes(candidate_manifest_bytes),
        "native_candidate_descriptor_sha256": sha256_bytes(candidate_descriptor_bytes),
        "native_candidate_manifest_identity": candidate_package["manifest"]["manifest_sha256"],
        "boundary": GATE_A_PACKAGE_BOUNDARY,
        "migration_boundary": GATE_A_MIGRATION_BOUNDARY,
    }
    descriptor_digest = sha256_bytes(canonical_json_bytes(descriptor))
    manifest = {
        "files": [{"path": path, "sha256": digest} for path, digest in sorted(state_digests.items())],
        "subpackages": [
            {
                "path": "native-candidate",
                "manifest_file_sha256": sha256_bytes(candidate_manifest_bytes),
                "manifest_identity": candidate_package["manifest"]["manifest_sha256"],
            }
        ],
        "descriptor_sha256": descriptor_digest,
        "release_authorized": False,
        "gate_a_complete": False,
        "representational_scope_complete": True,
        "boundary": GATE_A_PACKAGE_BOUNDARY,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    atomic_write_json(output_dir / "descriptor.json", descriptor)
    atomic_write_json(output_dir / "manifest.json", manifest)
    return {"descriptor": descriptor, "manifest": manifest}


def verify_gate_a_package(output_dir: Path) -> list[str]:
    """Verify package-level descriptor/manifest and child manifest bindings from disk."""
    errors: list[str] = []
    try:
        descriptor = json.loads((output_dir / "descriptor.json").read_text(encoding="utf-8"))
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read Gate-A descriptor/manifest: {exc}"]

    if descriptor.get("release_authorized") is not False or descriptor.get("gate_a_complete") is not False:
        errors.append("Gate-A descriptor authority/completion boundary mismatch")
    if descriptor.get("representational_scope_complete") is not True:
        errors.append("Gate-A descriptor lost representational completeness state")
    if descriptor.get("boundary") != GATE_A_PACKAGE_BOUNDARY:
        errors.append("Gate-A descriptor boundary mismatch")
    if manifest.get("descriptor_sha256") != sha256_bytes(canonical_json_bytes(descriptor)):
        errors.append("Gate-A descriptor digest mismatch")
    controlled_manifest = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if manifest.get("manifest_sha256") != sha256_bytes(canonical_json_bytes(controlled_manifest)):
        errors.append("Gate-A manifest identity mismatch")

    for item in manifest.get("files", []):
        if not isinstance(item, dict):
            errors.append("Gate-A manifest file entry must be an object")
            continue
        path = item.get("path")
        if not isinstance(path, str):
            errors.append("Gate-A manifest file path missing")
            continue
        file_path = output_dir / path
        if not file_path.is_file():
            errors.append(f"Gate-A manifest file missing: {path}")
        elif item.get("sha256") != sha256_bytes(file_path.read_bytes()):
            errors.append(f"Gate-A manifest file digest mismatch: {path}")

    candidate_manifest_path = output_dir / "native-candidate" / "manifest.json"
    if not candidate_manifest_path.is_file():
        errors.append("native-candidate manifest is missing")
    else:
        candidate_manifest_bytes = candidate_manifest_path.read_bytes()
        subpackages = manifest.get("subpackages")
        if not isinstance(subpackages, list) or len(subpackages) != 1:
            errors.append("Gate-A manifest requires exactly one native-candidate subpackage")
        else:
            subpackage = subpackages[0]
            if subpackage.get("manifest_file_sha256") != sha256_bytes(candidate_manifest_bytes):
                errors.append("native-candidate manifest file digest mismatch")
            try:
                candidate_manifest = json.loads(candidate_manifest_bytes)
            except json.JSONDecodeError:
                errors.append("native-candidate manifest is invalid JSON")
            else:
                if subpackage.get("manifest_identity") != candidate_manifest.get("manifest_sha256"):
                    errors.append("native-candidate manifest identity mismatch")

    return sorted(set(errors))
