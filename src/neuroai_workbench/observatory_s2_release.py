"""Graph-native S2 Observatory-v2 candidate compilation.

The Gate-A package is a migration/proof artifact. This module projects its public,
representationally complete state into the stable S2 release layout consumed by the
public Observatory API. Candidate compilation never authorizes or publishes the release.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .observatory_gate_a_package import verify_gate_a_package
from .util import atomic_write_bytes, atomic_write_json, canonical_json_bytes, sha256_bytes

S2_CANDIDATE_BOUNDARY = (
    "Graph-native S2 Observatory-v2 candidate only. Candidate integrity establishes artifact identity and "
    "migration lineage; it does not authorize publication, establish substantive truth, or confer institutional, "
    "clinical, regulatory, scientific, or conformance authority."
)

OBJECT_FILES = (
    "entities.jsonl",
    "sources.jsonl",
    "observations.jsonl",
    "assertions.jsonl",
    "events.jsonl",
    "relationships.jsonl",
    "candidates.jsonl",
    "reopening-decisions.jsonl",
)

_NATIVE_SOURCE_FILES = {
    "entities.jsonl": "entities.jsonl",
    "sources.jsonl": "sources.jsonl",
    "events.jsonl": "events.jsonl",
    "candidates.jsonl": "candidates.jsonl",
}

_MIGRATION_FILES = {
    "entity-predecessor-traces.jsonl": "native-candidate/entity-predecessor-traces.jsonl",
    "preserved-organizations.jsonl": "native-candidate/preserved-organizations.jsonl",
    "source-predecessor-traces.jsonl": "native-candidate/source-predecessor-traces.jsonl",
    "predecessor-observation-evidence.jsonl": "native-candidate/predecessor-observation-evidence.jsonl",
    "event-predecessor-traces.jsonl": "native-candidate/event-predecessor-traces.jsonl",
    "candidate-predecessor-traces.jsonl": "native-candidate/candidate-predecessor-traces.jsonl",
    "v16-adjudication-state.json": "v16-adjudication-state.json",
    "v17-successor-lineage.json": "v17-successor-lineage.json",
    "residual-predecessor-state.json": "residual-predecessor-state.json",
    "duplicate-container-proofs.json": "duplicate-container-proofs.json",
}


class ObservatoryS2ReleaseError(ValueError):
    """Raised when an S2 candidate cannot be compiled or verified exactly."""


def _load_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ObservatoryS2ReleaseError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ObservatoryS2ReleaseError(f"{label} must be a JSON object")
    return value


def _require_hex(value: Any, *, length: int, field: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(char not in "0123456789abcdef" for char in value):
        raise ObservatoryS2ReleaseError(f"{field} must be lowercase {length}-character hexadecimal")
    return value


def _copy_bound(source: Path, target: Path) -> str:
    if not source.is_file():
        raise ObservatoryS2ReleaseError(f"required Gate-A package file is missing: {source}")
    payload = source.read_bytes()
    atomic_write_bytes(target, payload)
    return sha256_bytes(payload)


def _jsonl_count(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _content_identity(files: list[dict[str, str]]) -> str:
    return sha256_bytes(canonical_json_bytes(files))


def write_observatory_v2_s2_candidate(
    gate_a_package_dir: Path,
    output_dir: Path,
    *,
    release_tag: str,
    s2_predecessor_release_tag: str,
    field_proof_sha256: str,
) -> dict[str, Any]:
    """Compile a verified Gate-A package into a clean, noncanonical S2 release candidate."""
    package_errors = verify_gate_a_package(gate_a_package_dir)
    if package_errors:
        raise ObservatoryS2ReleaseError(f"Gate-A package failed verification: {package_errors}")

    release_tag = release_tag.strip()
    predecessor_tag = s2_predecessor_release_tag.strip()
    if not release_tag or not predecessor_tag:
        raise ObservatoryS2ReleaseError("release_tag and s2_predecessor_release_tag must be non-empty")
    field_proof = _require_hex(field_proof_sha256, length=64, field="field_proof_sha256")

    gate_descriptor = _load_object(gate_a_package_dir / "descriptor.json", label="Gate-A descriptor")
    gate_manifest = _load_object(gate_a_package_dir / "manifest.json", label="Gate-A manifest")
    native_dir = gate_a_package_dir / "native-candidate"
    native_descriptor = _load_object(native_dir / "descriptor.json", label="native candidate descriptor")
    native_manifest = _load_object(native_dir / "manifest.json", label="native candidate manifest")

    if gate_descriptor.get("release_authorized") is not False:
        raise ObservatoryS2ReleaseError("Gate-A package must remain unauthorized")
    if gate_descriptor.get("representational_scope_complete") is not True:
        raise ObservatoryS2ReleaseError("Gate-A package must be representationally complete")
    if native_descriptor.get("release_authorized") is not False:
        raise ObservatoryS2ReleaseError("native candidate must remain unauthorized")

    output_dir.mkdir(parents=True, exist_ok=True)
    records_dir = output_dir / "records"
    migration_dir = output_dir / "migration"
    records_dir.mkdir(parents=True, exist_ok=True)
    migration_dir.mkdir(parents=True, exist_ok=True)

    file_digests: dict[str, str] = {}
    for filename in OBJECT_FILES:
        target = records_dir / filename
        native_filename = _NATIVE_SOURCE_FILES.get(filename)
        if native_filename is None:
            payload = b""
            atomic_write_bytes(target, payload)
            file_digests[f"records/{filename}"] = sha256_bytes(payload)
        else:
            file_digests[f"records/{filename}"] = _copy_bound(native_dir / native_filename, target)

    for target_name, source_relative in sorted(_MIGRATION_FILES.items()):
        file_digests[f"migration/{target_name}"] = _copy_bound(
            gate_a_package_dir / source_relative,
            migration_dir / target_name,
        )

    # Retain exact Gate-A package identities as release provenance without making the
    # Gate-A package itself the public release format.
    file_digests["migration/gate-a-descriptor.json"] = _copy_bound(
        gate_a_package_dir / "descriptor.json",
        migration_dir / "gate-a-descriptor.json",
    )
    file_digests["migration/gate-a-manifest.json"] = _copy_bound(
        gate_a_package_dir / "manifest.json",
        migration_dir / "gate-a-manifest.json",
    )

    file_entries = [{"path": path, "sha256": digest} for path, digest in sorted(file_digests.items())]
    content_sha256 = _content_identity(file_entries)
    candidate_id = f"OBS-V2-CAND-{content_sha256[:20].upper()}"

    class_counts = {
        "Entity": _jsonl_count(records_dir / "entities.jsonl"),
        "Source": _jsonl_count(records_dir / "sources.jsonl"),
        "Observation": _jsonl_count(records_dir / "observations.jsonl"),
        "Assertion": _jsonl_count(records_dir / "assertions.jsonl"),
        "Event": _jsonl_count(records_dir / "events.jsonl"),
        "Relationship": _jsonl_count(records_dir / "relationships.jsonl"),
        "Candidate": _jsonl_count(records_dir / "candidates.jsonl"),
        "ReopeningDecision": _jsonl_count(records_dir / "reopening-decisions.jsonl"),
    }

    descriptor = {
        "schema_version": "1",
        "release_type": "OBSERVATORY_V2_S2_CANDIDATE",
        "release_tag": release_tag,
        "candidate_id": candidate_id,
        "state": "NONCANONICAL_CANDIDATE",
        "canonical_publication_state": "NOT_AUTHORIZED",
        "release_authorized": False,
        "published": False,
        "record_counts": class_counts,
        "candidate_content_sha256": content_sha256,
        "workbench_compatibility_version": gate_descriptor.get("workbench_compatibility_version"),
        "producer_workbench_commit": _require_hex(
            gate_descriptor.get("producer_workbench_commit"), length=40, field="producer_workbench_commit"
        ),
        "runtime_execution_pin": _require_hex(
            gate_descriptor.get("runtime_execution_pin"), length=40, field="runtime_execution_pin"
        ),
        "observatory_graph_schema_version": str(gate_descriptor.get("observatory_graph_schema_version") or ""),
        "s2_predecessor": {
            "release_tag": predecessor_tag,
            "commit": _require_hex(
                gate_descriptor.get("s2_predecessor_commit"), length=40, field="s2_predecessor_commit"
            ),
        },
        "migration_proof": {
            "field_proof_sha256": field_proof,
            "gate_a_manifest_sha256": _require_hex(
                gate_manifest.get("manifest_sha256"), length=64, field="gate_a_manifest_sha256"
            ),
            "gate_a_descriptor_sha256": sha256_bytes(canonical_json_bytes(gate_descriptor)),
            "native_candidate_manifest_sha256": _require_hex(
                native_manifest.get("manifest_sha256"), length=64, field="native_candidate_manifest_sha256"
            ),
        },
        "boundary": S2_CANDIDATE_BOUNDARY,
    }
    if not descriptor["observatory_graph_schema_version"].strip():
        raise ObservatoryS2ReleaseError("observatory_graph_schema_version must be present in Gate-A package")

    descriptor_sha256 = sha256_bytes(canonical_json_bytes(descriptor))
    manifest = {
        "schema_version": "1",
        "candidate_id": candidate_id,
        "candidate_content_sha256": content_sha256,
        "files": file_entries,
        "descriptor_sha256": descriptor_sha256,
        "release_authorized": False,
        "published": False,
        "boundary": S2_CANDIDATE_BOUNDARY,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    atomic_write_json(output_dir / "descriptor.json", descriptor)
    atomic_write_json(output_dir / "manifest.json", manifest)

    errors = verify_observatory_v2_s2_candidate(output_dir)
    if errors:
        raise ObservatoryS2ReleaseError(f"generated S2 candidate failed verification: {errors}")
    return {"descriptor": descriptor, "manifest": manifest}


def verify_observatory_v2_s2_candidate(release_dir: Path) -> list[str]:
    """Verify an S2 v2 candidate from disk without conferring publication authority."""
    errors: list[str] = []
    try:
        descriptor = _load_object(release_dir / "descriptor.json", label="S2 descriptor")
        manifest = _load_object(release_dir / "manifest.json", label="S2 manifest")
    except ObservatoryS2ReleaseError as exc:
        return [str(exc)]

    if descriptor.get("release_type") != "OBSERVATORY_V2_S2_CANDIDATE":
        errors.append("S2 candidate release_type mismatch")
    if descriptor.get("state") != "NONCANONICAL_CANDIDATE":
        errors.append("S2 candidate state mismatch")
    if descriptor.get("release_authorized") is not False or descriptor.get("published") is not False:
        errors.append("S2 candidate must remain unauthorized and unpublished")
    if descriptor.get("canonical_publication_state") != "NOT_AUTHORIZED":
        errors.append("S2 candidate canonical publication state mismatch")
    if descriptor.get("boundary") != S2_CANDIDATE_BOUNDARY or manifest.get("boundary") != S2_CANDIDATE_BOUNDARY:
        errors.append("S2 candidate boundary mismatch")

    if manifest.get("descriptor_sha256") != sha256_bytes(canonical_json_bytes(descriptor)):
        errors.append("S2 candidate descriptor digest mismatch")
    controlled_manifest = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if manifest.get("manifest_sha256") != sha256_bytes(canonical_json_bytes(controlled_manifest)):
        errors.append("S2 candidate manifest identity mismatch")

    file_entries = manifest.get("files")
    if not isinstance(file_entries, list):
        return sorted(set(errors + ["S2 candidate files manifest is missing"]))
    observed_entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in file_entries:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            errors.append("S2 candidate file entry is invalid")
            continue
        path = str(item["path"])
        if path in seen:
            errors.append(f"duplicate S2 candidate file path {path}")
            continue
        seen.add(path)
        file_path = release_dir / path
        if not file_path.is_file():
            errors.append(f"S2 candidate file missing: {path}")
            continue
        observed = sha256_bytes(file_path.read_bytes())
        if item.get("sha256") != observed:
            errors.append(f"S2 candidate file digest mismatch: {path}")
        observed_entries.append({"path": path, "sha256": observed})

    observed_entries.sort(key=lambda item: item["path"])
    content_sha256 = _content_identity(observed_entries)
    if manifest.get("candidate_content_sha256") != content_sha256:
        errors.append("S2 candidate content identity mismatch")
    if descriptor.get("candidate_content_sha256") != content_sha256:
        errors.append("S2 descriptor content identity mismatch")
    expected_candidate_id = f"OBS-V2-CAND-{content_sha256[:20].upper()}"
    if descriptor.get("candidate_id") != expected_candidate_id or manifest.get("candidate_id") != expected_candidate_id:
        errors.append("S2 candidate_id does not match content identity")

    required_record_paths = {f"records/{filename}" for filename in OBJECT_FILES}
    if not required_record_paths.issubset(seen):
        errors.append("S2 candidate does not expose the complete stable object-file surface")

    counts = descriptor.get("record_counts")
    expected_counts = {
        "Entity": _jsonl_count(release_dir / "records/entities.jsonl"),
        "Source": _jsonl_count(release_dir / "records/sources.jsonl"),
        "Observation": _jsonl_count(release_dir / "records/observations.jsonl"),
        "Assertion": _jsonl_count(release_dir / "records/assertions.jsonl"),
        "Event": _jsonl_count(release_dir / "records/events.jsonl"),
        "Relationship": _jsonl_count(release_dir / "records/relationships.jsonl"),
        "Candidate": _jsonl_count(release_dir / "records/candidates.jsonl"),
        "ReopeningDecision": _jsonl_count(release_dir / "records/reopening-decisions.jsonl"),
    }
    if counts != expected_counts:
        errors.append("S2 candidate record-count reconciliation mismatch")

    return sorted(set(errors))
