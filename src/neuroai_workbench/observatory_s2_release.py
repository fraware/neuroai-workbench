"""Graph-native S2 Observatory-v2 candidate compilation.

The Gate-A package is a migration/proof artifact. This module projects its public,
representationally complete state into the stable S2 release layout consumed by the
public Observatory API. Candidate compilation requires the separate mechanical Gate-A
PASS decision and never authorizes or publishes the resulting release.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from .observatory_gate_a_package import verify_gate_a_package
from .util import atomic_write_bytes, atomic_write_json, canonical_json_bytes, sha256_bytes

S2_CANDIDATE_BOUNDARY = (
    "Graph-native S2 Observatory-v2 candidate only. Candidate integrity establishes artifact identity and "
    "migration lineage; it does not authorize publication, establish substantive truth, or confer institutional, "
    "clinical, regulatory, scientific, or conformance authority."
)
MECHANICAL_GATE_A_DECISION = "PASS_REPRESENTATIONAL_MIGRATION_MECHANICALLY_COMPLETE"
FROZEN_INPUT_ROLES = frozenset({"V14", "V16", "DELTA16", "V17", "PRIMA17", "SOURCE_REGISTER14", "MONITOR15"})

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

OBJECT_CLASS_BY_FILE = {
    "entities.jsonl": "Entity",
    "sources.jsonl": "Source",
    "observations.jsonl": "Observation",
    "assertions.jsonl": "Assertion",
    "events.jsonl": "Event",
    "relationships.jsonl": "Relationship",
    "candidates.jsonl": "Candidate",
    "reopening-decisions.jsonl": "ReopeningDecision",
}

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

_GATE_A_MIGRATION_FILES = (
    "gate-a-descriptor.json",
    "gate-a-manifest.json",
    "gate-a-decision.json",
)

CANDIDATE_FILE_PATHS = frozenset(
    {f"records/{filename}" for filename in OBJECT_FILES}
    | {f"migration/{filename}" for filename in _MIGRATION_FILES}
    | {f"migration/{filename}" for filename in _GATE_A_MIGRATION_FILES}
)


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


def _content_identity(files: list[dict[str, str]]) -> str:
    return sha256_bytes(canonical_json_bytes(files))


def _record_digest(record: dict[str, Any], field: str) -> str:
    controlled = {key: value for key, value in record.items() if key != field}
    return sha256_bytes(canonical_json_bytes(controlled))


def _frozen_inputs(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != FROZEN_INPUT_ROLES:
        raise ObservatoryS2ReleaseError("Gate-A descriptor must bind exactly the seven frozen input roles")
    return {
        role: _require_hex(value[role], length=64, field=f"frozen input {role}") for role in sorted(FROZEN_INPUT_ROLES)
    }


def _safe_candidate_path(release_dir: Path, raw_path: str) -> Path:
    path = PurePosixPath(raw_path)
    if path.is_absolute() or not path.parts or ".." in path.parts or path.as_posix() != raw_path:
        raise ObservatoryS2ReleaseError(f"unsafe S2 candidate file path: {raw_path}")
    root = release_dir.resolve()
    target = release_dir.joinpath(*path.parts)
    resolved = target.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ObservatoryS2ReleaseError(f"S2 candidate file escapes release root: {raw_path}")
    return target


def _jsonl_count_and_errors(path: Path, *, expected_class: str) -> tuple[int, list[str]]:
    if not path.is_file():
        return 0, [f"S2 record file missing: {path.name}"]
    count = 0
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return 0, [f"cannot read S2 record file {path.name}: {exc}"]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        count += 1
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}:{line_number}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(value, dict):
            errors.append(f"{path.name}:{line_number}: graph record must be a JSON object")
        elif value.get("object_class") != expected_class:
            errors.append(
                f"{path.name}:{line_number}: expected object_class {expected_class}, got {value.get('object_class')!r}"
            )
    return count, errors


def _verify_gate_a_decision(
    decision: dict[str, Any],
    *,
    gate_descriptor: dict[str, Any],
    gate_manifest: dict[str, Any],
) -> dict[str, Any]:
    decision_id = str(decision.get("decision_sha256") or "")
    if decision_id != _record_digest(decision, "decision_sha256"):
        raise ObservatoryS2ReleaseError("Gate-A decision digest mismatch")
    if decision.get("decision_type") != "OBSERVATORY_V2_GATE_A_MECHANICAL_DECISION":
        raise ObservatoryS2ReleaseError("Gate-A decision type mismatch")
    if decision.get("decision") != MECHANICAL_GATE_A_DECISION:
        raise ObservatoryS2ReleaseError("Gate-A decision is not mechanical PASS")
    if decision.get("gate_a_complete") is not True:
        raise ObservatoryS2ReleaseError("Gate-A decision does not mark the mechanical gate complete")
    if decision.get("release_authorized") is not False:
        raise ObservatoryS2ReleaseError("Gate-A decision must not authorize publication")
    if decision.get("representational_scope_complete") is not True:
        raise ObservatoryS2ReleaseError("Gate-A decision lost representational completeness")
    if decision.get("native_v2_materialization_complete") is not False:
        raise ObservatoryS2ReleaseError("Gate-A decision must not claim complete native materialization")

    manifest_identity = _require_hex(gate_manifest.get("manifest_sha256"), length=64, field="Gate-A manifest identity")
    descriptor_identity = _require_hex(
        gate_manifest.get("descriptor_sha256"), length=64, field="Gate-A descriptor identity"
    )
    if decision.get("gate_a_package_manifest_sha256") != manifest_identity:
        raise ObservatoryS2ReleaseError("Gate-A decision/package manifest binding mismatch")
    if decision.get("gate_a_package_descriptor_sha256") != descriptor_identity:
        raise ObservatoryS2ReleaseError("Gate-A decision/package descriptor binding mismatch")
    if descriptor_identity != sha256_bytes(canonical_json_bytes(gate_descriptor)):
        raise ObservatoryS2ReleaseError("Gate-A package descriptor digest mismatch")
    controlled_manifest = {key: value for key, value in gate_manifest.items() if key != "manifest_sha256"}
    if manifest_identity != sha256_bytes(canonical_json_bytes(controlled_manifest)):
        raise ObservatoryS2ReleaseError("Gate-A package manifest identity mismatch")

    for field in ("producer_workbench_commit", "runtime_execution_pin", "s2_predecessor_commit"):
        if decision.get(field) != gate_descriptor.get(field):
            raise ObservatoryS2ReleaseError(f"Gate-A decision {field} binding mismatch")
    if str(decision.get("observatory_graph_schema_version") or "") != str(
        gate_descriptor.get("observatory_graph_schema_version") or ""
    ):
        raise ObservatoryS2ReleaseError("Gate-A decision graph schema binding mismatch")
    _require_hex(decision.get("field_proof_sha256"), length=64, field="field_proof_sha256")
    return decision


def write_observatory_v2_s2_candidate(
    gate_a_package_dir: Path,
    gate_a_decision_path: Path,
    output_dir: Path,
    *,
    release_tag: str,
    s2_predecessor_release_tag: str,
) -> dict[str, Any]:
    """Compile a mechanically closed Gate-A package into a noncanonical S2 release candidate."""
    package_errors = verify_gate_a_package(gate_a_package_dir)
    if package_errors:
        raise ObservatoryS2ReleaseError(f"Gate-A package failed verification: {package_errors}")

    release_tag = release_tag.strip()
    predecessor_tag = s2_predecessor_release_tag.strip()
    if not release_tag or not predecessor_tag:
        raise ObservatoryS2ReleaseError("release_tag and s2_predecessor_release_tag must be non-empty")

    gate_descriptor = _load_object(gate_a_package_dir / "descriptor.json", label="Gate-A descriptor")
    gate_manifest = _load_object(gate_a_package_dir / "manifest.json", label="Gate-A manifest")
    gate_decision = _load_object(gate_a_decision_path, label="Gate-A decision")
    _verify_gate_a_decision(gate_decision, gate_descriptor=gate_descriptor, gate_manifest=gate_manifest)
    frozen_inputs = _frozen_inputs(gate_descriptor.get("inputs"))

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
            atomic_write_bytes(target, b"")
            file_digests[f"records/{filename}"] = sha256_bytes(b"")
        else:
            file_digests[f"records/{filename}"] = _copy_bound(native_dir / native_filename, target)

    for target_name, source_relative in sorted(_MIGRATION_FILES.items()):
        file_digests[f"migration/{target_name}"] = _copy_bound(
            gate_a_package_dir / source_relative,
            migration_dir / target_name,
        )
    file_digests["migration/gate-a-descriptor.json"] = _copy_bound(
        gate_a_package_dir / "descriptor.json", migration_dir / "gate-a-descriptor.json"
    )
    file_digests["migration/gate-a-manifest.json"] = _copy_bound(
        gate_a_package_dir / "manifest.json", migration_dir / "gate-a-manifest.json"
    )
    file_digests["migration/gate-a-decision.json"] = _copy_bound(
        gate_a_decision_path, migration_dir / "gate-a-decision.json"
    )

    file_entries = [{"path": path, "sha256": digest} for path, digest in sorted(file_digests.items())]
    if {item["path"] for item in file_entries} != CANDIDATE_FILE_PATHS:
        raise ObservatoryS2ReleaseError("internal S2 candidate file surface does not match governed allowlist")
    content_sha256 = _content_identity(file_entries)
    candidate_id = f"OBS-V2-CAND-{content_sha256[:20].upper()}"

    class_counts: dict[str, int] = {}
    for filename, object_class in OBJECT_CLASS_BY_FILE.items():
        count, record_errors = _jsonl_count_and_errors(records_dir / filename, expected_class=object_class)
        if record_errors:
            raise ObservatoryS2ReleaseError("invalid native graph record surface: " + "; ".join(record_errors))
        class_counts[object_class] = count

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
        "workbench_compatibility_version": str(gate_descriptor.get("workbench_compatibility_version") or ""),
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
        "frozen_inputs": frozen_inputs,
        "migration_proof": {
            "field_proof_sha256": _require_hex(
                gate_decision.get("field_proof_sha256"), length=64, field="field_proof_sha256"
            ),
            "gate_a_decision_sha256": _require_hex(
                gate_decision.get("decision_sha256"), length=64, field="gate_a_decision_sha256"
            ),
            "gate_a_manifest_sha256": _require_hex(
                gate_manifest.get("manifest_sha256"), length=64, field="gate_a_manifest_sha256"
            ),
            "gate_a_descriptor_sha256": _require_hex(
                gate_manifest.get("descriptor_sha256"), length=64, field="gate_a_descriptor_sha256"
            ),
            "native_candidate_manifest_sha256": _require_hex(
                native_manifest.get("manifest_sha256"), length=64, field="native_candidate_manifest_sha256"
            ),
        },
        "boundary": S2_CANDIDATE_BOUNDARY,
    }
    if not descriptor["workbench_compatibility_version"].strip():
        raise ObservatoryS2ReleaseError("workbench_compatibility_version must be present in Gate-A package")
    if not descriptor["observatory_graph_schema_version"].strip():
        raise ObservatoryS2ReleaseError("observatory_graph_schema_version must be present in Gate-A package")

    manifest = {
        "schema_version": "1",
        "candidate_id": candidate_id,
        "candidate_content_sha256": content_sha256,
        "files": file_entries,
        "descriptor_sha256": sha256_bytes(canonical_json_bytes(descriptor)),
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

    try:
        _require_hex(descriptor.get("producer_workbench_commit"), length=40, field="producer_workbench_commit")
        _require_hex(descriptor.get("runtime_execution_pin"), length=40, field="runtime_execution_pin")
        predecessor = descriptor.get("s2_predecessor")
        if not isinstance(predecessor, dict) or not str(predecessor.get("release_tag") or "").strip():
            errors.append("S2 candidate predecessor release identity is missing")
        else:
            _require_hex(predecessor.get("commit"), length=40, field="s2_predecessor_commit")
        if not str(descriptor.get("workbench_compatibility_version") or "").strip():
            errors.append("S2 candidate Workbench compatibility line is missing")
        if not str(descriptor.get("observatory_graph_schema_version") or "").strip():
            errors.append("S2 candidate graph schema version is missing")
        _frozen_inputs(descriptor.get("frozen_inputs"))
        proof = descriptor.get("migration_proof")
        if not isinstance(proof, dict):
            errors.append("S2 candidate migration proof binding is missing")
        else:
            for field in (
                "field_proof_sha256",
                "gate_a_decision_sha256",
                "gate_a_manifest_sha256",
                "gate_a_descriptor_sha256",
                "native_candidate_manifest_sha256",
            ):
                _require_hex(proof.get(field), length=64, field=field)
    except ObservatoryS2ReleaseError as exc:
        errors.append(str(exc))

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
        raw_path = str(item["path"])
        if raw_path in seen:
            errors.append(f"duplicate S2 candidate file path {raw_path}")
            continue
        seen.add(raw_path)
        if raw_path not in CANDIDATE_FILE_PATHS:
            errors.append(f"S2 candidate file path is outside governed allowlist: {raw_path}")
            continue
        try:
            file_path = _safe_candidate_path(release_dir, raw_path)
        except ObservatoryS2ReleaseError as exc:
            errors.append(str(exc))
            continue
        if not file_path.is_file():
            errors.append(f"S2 candidate file missing: {raw_path}")
            continue
        observed = sha256_bytes(file_path.read_bytes())
        if item.get("sha256") != observed:
            errors.append(f"S2 candidate file digest mismatch: {raw_path}")
        observed_entries.append({"path": raw_path, "sha256": observed})

    if seen != CANDIDATE_FILE_PATHS:
        missing = sorted(CANDIDATE_FILE_PATHS - seen)
        extra = sorted(seen - CANDIDATE_FILE_PATHS)
        errors.append(f"S2 candidate file surface mismatch: missing={missing}, extra={extra}")

    observed_entries.sort(key=lambda item: item["path"])
    content_sha256 = _content_identity(observed_entries)
    if manifest.get("candidate_content_sha256") != content_sha256:
        errors.append("S2 candidate content identity mismatch")
    if descriptor.get("candidate_content_sha256") != content_sha256:
        errors.append("S2 descriptor content identity mismatch")
    expected_candidate_id = f"OBS-V2-CAND-{content_sha256[:20].upper()}"
    if descriptor.get("candidate_id") != expected_candidate_id or manifest.get("candidate_id") != expected_candidate_id:
        errors.append("S2 candidate_id does not match content identity")

    expected_counts: dict[str, int] = {}
    for filename, object_class in OBJECT_CLASS_BY_FILE.items():
        count, record_errors = _jsonl_count_and_errors(release_dir / "records" / filename, expected_class=object_class)
        expected_counts[object_class] = count
        errors.extend(record_errors)
    if descriptor.get("record_counts") != expected_counts:
        errors.append("S2 candidate record-count reconciliation mismatch")

    try:
        copied_gate_descriptor = _load_object(
            release_dir / "migration/gate-a-descriptor.json", label="copied Gate-A descriptor"
        )
        copied_gate_manifest = _load_object(
            release_dir / "migration/gate-a-manifest.json", label="copied Gate-A manifest"
        )
        copied_gate_decision = _load_object(
            release_dir / "migration/gate-a-decision.json", label="copied Gate-A decision"
        )
        _verify_gate_a_decision(
            copied_gate_decision,
            gate_descriptor=copied_gate_descriptor,
            gate_manifest=copied_gate_manifest,
        )
        proof = descriptor.get("migration_proof") or {}
        if proof.get("gate_a_decision_sha256") != copied_gate_decision.get("decision_sha256"):
            errors.append("S2 descriptor Gate-A decision binding mismatch")
        if proof.get("field_proof_sha256") != copied_gate_decision.get("field_proof_sha256"):
            errors.append("S2 descriptor field-proof binding mismatch")
        if descriptor.get("frozen_inputs") != copied_gate_descriptor.get("inputs"):
            errors.append("S2 descriptor frozen-input binding mismatch")
    except ObservatoryS2ReleaseError as exc:
        errors.append(str(exc))

    return sorted(set(errors))
