from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

from .util import canonical_json_bytes, ensure_identifier, load_json, sha256_bytes

OPERATIONS_RESOURCE_PACKAGE = "neuroai_workbench.resources.operations"
MANIFEST_SCHEMA = "ASSESSMENT_DEPENDENCY_MANIFEST.schema.json"

DEPENDENCY_ROLES = frozenset(
    {
        "IDENTITY_DEFINING",
        "FINDING_SUPPORTING",
        "GAP_SUPPORTING",
        "DECISION_SUPPORTING",
        "CONTEXTUAL_ONLY",
        "REOPENING_TRIGGER",
    }
)

TARGET_KINDS = frozenset(
    {
        "ORGANIZATION",
        "LEGAL_ENTITY",
        "SYSTEM",
        "CONFIGURATION",
        "MODEL",
        "FIRMWARE",
        "HARDWARE",
        "SOFTWARE",
        "TRIAL",
        "PARTICIPANT_POPULATION",
        "SITE",
        "ENDPOINT",
        "REGULATORY_RECORD",
        "JURISDICTION",
        "SUPPLIER",
        "INFRASTRUCTURE",
        "EVIDENCE_OBJECT",
        "SOURCE_RECORD",
        "OBSERVATORY_RELEASE",
        "EVIDENCE_CUTOFF",
    }
)

RESOLUTION_STATES = frozenset({"RESOLVED", "UNKNOWN", "INACCESSIBLE", "PARTIAL"})

MANIFEST_BOUNDARY = (
    "Dependency manifests declare typed links between an exact assessment boundary and observatory objects. "
    "Resolution state UNKNOWN or INACCESSIBLE preserves uncertainty; it does not infer failure or substantive truth."
)

REFERENCE_MANIFESTS: dict[str, str] = {
    "PRIMA-PUBLIC-2026-001": "PRIMA-PUBLIC-2026-001.dependencies.json",
    "PILOT-01-BRAINGATE2-T15-v4.1.5": "PILOT-01-BRAINGATE2-T15-v4.1.5.dependencies.json",
    "PILOT-02-FDA-ADBS-v4.1.4": "PILOT-02-FDA-ADBS-v4.1.4.dependencies.json",
    "PILOT-05-BRAIN2QWERTY-v4.1.3": "PILOT-05-BRAIN2QWERTY-v4.1.3.dependencies.json",
}


def _schema(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any], json.loads(files(OPERATIONS_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8"))
    )


def _schema_errors(value: Any, schema_name: str) -> list[dict[str, Any]]:
    validator = Draft202012Validator(_schema(schema_name))
    return [
        {
            "code": "SCHEMA_ERROR",
            "path": ".".join(str(part) for part in error.absolute_path),
            "message": error.message,
        }
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def _duplicate_dependency_ids(dependencies: list[Any]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in dependencies:
        if not isinstance(item, dict):
            continue
        dependency_id = item.get("dependency_id")
        if not isinstance(dependency_id, str):
            continue
        if dependency_id in seen:
            duplicates.add(dependency_id)
        seen.add(dependency_id)
    return sorted(duplicates)


def load_manifest(path: Path) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict):
        raise ValueError("Assessment dependency manifest must be a JSON object")
    return value


def validate_manifest(value: dict[str, Any]) -> dict[str, Any]:
    errors = list(_schema_errors(value, MANIFEST_SCHEMA))
    warnings: list[dict[str, Any]] = []
    metadata = value.get("metadata", {})
    assessment_id = metadata.get("assessment_id") if isinstance(metadata, dict) else None
    dependencies = value.get("dependencies", [])
    if isinstance(dependencies, list):
        duplicates = _duplicate_dependency_ids(dependencies)
        if duplicates:
            errors.append({"code": "DUPLICATE_IDENTIFIER", "path": "dependencies", "identifiers": duplicates})
        unresolved_identity = [
            item.get("dependency_id")
            for item in dependencies
            if isinstance(item, dict)
            and item.get("dependency_role") == "IDENTITY_DEFINING"
            and item.get("resolution_state") in {"UNKNOWN", "INACCESSIBLE"}
        ]
        if unresolved_identity:
            warnings.append(
                {
                    "code": "UNRESOLVED_IDENTITY_DEPENDENCY",
                    "dependency_ids": unresolved_identity,
                    "detail": "Unresolved identity dependencies remain explicit; they do not invalidate the manifest.",
                }
            )
    counts = {
        "dependencies": len(dependencies) if isinstance(dependencies, list) else 0,
        "identity_defining": sum(
            1 for item in dependencies if isinstance(item, dict) and item.get("dependency_role") == "IDENTITY_DEFINING"
        )
        if isinstance(dependencies, list)
        else 0,
        "reopening_trigger": sum(
            1 for item in dependencies if isinstance(item, dict) and item.get("dependency_role") == "REOPENING_TRIGGER"
        )
        if isinstance(dependencies, list)
        else 0,
        "unknown_or_inaccessible": sum(
            1
            for item in dependencies
            if isinstance(item, dict) and item.get("resolution_state") in {"UNKNOWN", "INACCESSIBLE"}
        )
        if isinstance(dependencies, list)
        else 0,
    }
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "assessment_id": assessment_id,
        "counts": counts,
        "canonical_sha256": sha256_bytes(canonical_json_bytes(value)),
        "boundary": MANIFEST_BOUNDARY,
    }


def validate_manifest_file(path: Path) -> dict[str, Any]:
    return validate_manifest(load_manifest(path))


def reference_manifest_dir(root: Path | None = None) -> Path:
    base = root or Path(__file__).resolve().parents[2]
    return base / "examples" / "assessments" / "dependencies"


def reference_manifest_path(assessment_id: str, root: Path | None = None) -> Path:
    ensure_identifier(assessment_id, "assessment ID")
    filename = REFERENCE_MANIFESTS.get(assessment_id)
    if filename is None:
        raise ValueError(f"No reference dependency manifest registered for assessment {assessment_id!r}")
    return reference_manifest_dir(root) / filename


def load_reference_manifest(assessment_id: str, root: Path | None = None) -> dict[str, Any]:
    return load_manifest(reference_manifest_path(assessment_id, root))


def load_all_reference_manifests(root: Path | None = None) -> dict[str, dict[str, Any]]:
    manifests: dict[str, dict[str, Any]] = {}
    for assessment_id in REFERENCE_MANIFESTS:
        manifest = load_reference_manifest(assessment_id, root)
        metadata = manifest.get("metadata", {})
        key = metadata.get("assessment_id") if isinstance(metadata, dict) else assessment_id
        manifests[str(key)] = manifest
    return manifests


def summarize_manifest(value: dict[str, Any]) -> dict[str, Any]:
    report = validate_manifest(value)
    metadata = value.get("metadata", {}) if isinstance(value.get("metadata"), dict) else {}
    dependencies = value.get("dependencies", []) if isinstance(value.get("dependencies"), list) else []
    by_role = {role: 0 for role in sorted(DEPENDENCY_ROLES)}
    by_resolution = {state: 0 for state in sorted(RESOLUTION_STATES)}
    for item in dependencies:
        if not isinstance(item, dict):
            continue
        role = item.get("dependency_role")
        if role in by_role:
            by_role[role] += 1
        resolution = item.get("resolution_state")
        if resolution in by_resolution:
            by_resolution[resolution] += 1
    return {
        "valid": report["valid"],
        "assessment_id": metadata.get("assessment_id"),
        "manifest_id": metadata.get("manifest_id"),
        "system_id": metadata.get("system_id"),
        "configuration_id": metadata.get("configuration_id"),
        "evidence_cutoff": metadata.get("evidence_cutoff"),
        "counts": report["counts"],
        "by_role": by_role,
        "by_resolution": by_resolution,
        "withheld_claims": value.get("withheld_claims", []),
        "boundary": MANIFEST_BOUNDARY,
    }


def match_dependency(
    *,
    target_kind: str,
    target_ref: str,
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return manifest dependencies that match a target kind and reference token."""
    ensure_identifier(target_ref, "target reference")
    if target_kind not in TARGET_KINDS:
        raise ValueError(f"Unsupported target kind {target_kind!r}")
    dependencies = manifest.get("dependencies", [])
    if not isinstance(dependencies, list):
        return []
    matches: list[dict[str, Any]] = []
    normalized_ref = target_ref.casefold()
    for item in dependencies:
        if not isinstance(item, dict):
            continue
        if item.get("target_kind") != target_kind:
            continue
        item_ref = item.get("target_ref")
        if not isinstance(item_ref, str):
            continue
        if item_ref == target_ref or item_ref.casefold() == normalized_ref:
            matches.append(item)
    return matches
