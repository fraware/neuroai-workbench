from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .util import atomic_write_json, canonical_json_bytes, sha256_bytes, sha256_file

REQUIRED_LISTS = (
    "organizations",
    "organization_resolution",
    "regional_expansion",
    "capital_and_ownership_events",
    "representative_model_records",
    "model_and_dataset_registry",
    "trial_site_relationships",
    "participant_authority_relationships",
    "supplier_dependency_relationships",
    "sources",
)

ID_FIELDS = {
    "organizations": "organization_id",
    "organization_resolution": "resolution_id",
    "regional_expansion": "regional_record_id",
    "capital_and_ownership_events": "event_id",
    "representative_model_records": "model_id",
    "model_and_dataset_registry": "registry_id",
    "trial_site_relationships": "relationship_id",
    "participant_authority_relationships": "authority_id",
    "supplier_dependency_relationships": "dependency_id",
    "sources": "source_id",
}


def load_release(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Observatory release must be a JSON object")
    return value


def _ids(records: list[dict[str, Any]], field: str) -> list[str]:
    return [record.get(field) for record in records if isinstance(record, dict)]


def validate_release(value: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    metadata = value.get("metadata")
    if not isinstance(metadata, dict):
        errors.append({"code": "METADATA_REQUIRED", "path": "metadata"})
        metadata = {}
    for field in ("title", "version", "evidence_cutoff", "status", "north_star"):
        if not metadata.get(field):
            errors.append({"code": "METADATA_FIELD_REQUIRED", "path": f"metadata.{field}"})
    for key in REQUIRED_LISTS:
        if not isinstance(value.get(key), list):
            errors.append({"code": "LIST_REQUIRED", "path": key})
    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings, "counts": {}}

    counts: dict[str, int] = {}
    for key, field in ID_FIELDS.items():
        records = value[key]
        ids = _ids(records, field)
        missing = [i for i, identifier in enumerate(ids) if not identifier]
        if missing:
            errors.append({"code": "IDENTIFIER_REQUIRED", "path": key, "rows": missing})
        duplicates = sorted({identifier for identifier in ids if identifier and ids.count(identifier) > 1})
        if duplicates:
            errors.append({"code": "DUPLICATE_IDENTIFIER", "path": key, "identifiers": duplicates})
        counts[key] = len(records)

    source_ids = {record["source_id"] for record in value["sources"] if record.get("source_id")}
    for key in REQUIRED_LISTS:
        if key == "sources":
            continue
        for index, record in enumerate(value[key]):
            for source_id in record.get("source_ids", []):
                if source_id not in source_ids:
                    errors.append({"code": "UNRESOLVED_SOURCE_REFERENCE", "path": f"{key}[{index}].source_ids", "source_id": source_id})

    organization_ids = {record["organization_id"] for record in value["organizations"] if record.get("organization_id")}
    for index, record in enumerate(value["organization_resolution"]):
        if record.get("organization_id") not in organization_ids:
            errors.append({"code": "UNRESOLVED_ORGANIZATION_REFERENCE", "path": f"organization_resolution[{index}].organization_id"})
    for index, record in enumerate(value["regional_expansion"]):
        if record.get("organization_id") not in organization_ids:
            errors.append({"code": "UNRESOLVED_ORGANIZATION_REFERENCE", "path": f"regional_expansion[{index}].organization_id"})

    coverage = value.get("coverage", {}).get("v1_4_effective_counts", {})
    denominator = coverage.get("active_nonlegacy_organization_denominator")
    verified = coverage.get("current_verified_active_nonlegacy")
    if isinstance(denominator, int) and denominator > 0 and isinstance(verified, int):
        computed = round(verified / denominator, 4)
        declared = coverage.get("verification_rate")
        if declared != computed:
            errors.append({"code": "VERIFICATION_RATE_MISMATCH", "declared": declared, "computed": computed})
    else:
        warnings.append({"code": "COVERAGE_DENOMINATOR_UNAVAILABLE"})

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": counts,
        "canonical_sha256": sha256_bytes(canonical_json_bytes(value)),
        "boundary": "Mechanical validation does not establish scientific validity, authorization, deployment approval or system conformance.",
    }


def summarize_release(value: dict[str, Any]) -> dict[str, Any]:
    report = validate_release(value)
    coverage = value.get("coverage", {}).get("v1_4_effective_counts", {})
    exits = value.get("coverage", {}).get("exit_conditions", [])
    return {
        "metadata": value.get("metadata", {}),
        "valid": report["valid"],
        "counts": report["counts"],
        "coverage": coverage,
        "exit_condition_states": {item.get("condition"): item.get("state") for item in exits},
        "boundaries": [
            "Counts apply only to declared source universes.",
            "Company announcements remain company evidence unless independently corroborated.",
            "Organization, financing, site and software records do not establish conformance.",
        ],
    }


def queue_release(value: dict[str, Any]) -> dict[str, Any]:
    org_queue = [
        {"organization_id": item.get("organization_id"), "name": item.get("canonical_name"), "verification_state": item.get("verification_state")}
        for item in value.get("organizations", [])
        if item.get("verification_state") not in {"CURRENT_VERIFIED", "CURRENT_VERIFIED_RESCOPED", "CURRENT_VERIFIED_CORRECTED", "LEGACY_ONLY", "NON_ORGANIZATION_PROVENANCE_NODE", "HISTORICAL_ARCHIVED"}
    ]
    source_queue = [
        {"source_id": item.get("source_id"), "title": item.get("title"), "verification_state": item.get("verification_state")}
        for item in value.get("sources", [])
        if item.get("verification_state") not in {"CURRENT_VERIFIED", "HISTORICAL_INPUT"}
    ]
    return {
        "organization_queue": org_queue,
        "source_queue": source_queue,
        "counts": {"organizations": len(org_queue), "sources": len(source_queue)},
        "boundary": "Queue closure requires evidence; unresolved records are not automatically downgraded or upgraded.",
    }


def import_release(workspace: Path, release_path: Path) -> dict[str, Any]:
    value = load_release(release_path)
    report = validate_release(value)
    if not report["valid"]:
        raise ValueError("Observatory release failed validation")
    version = value["metadata"]["version"]
    target = workspace / "observatory" / "releases" / version
    target.mkdir(parents=True, exist_ok=True)
    output = target / "release.json"
    atomic_write_json(output, value)
    manifest = {
        "version": version,
        "evidence_cutoff": value["metadata"]["evidence_cutoff"],
        "source_file": str(release_path),
        "source_sha256": sha256_file(release_path),
        "stored_sha256": sha256_file(output),
        "validation": report,
        "boundary": "Import records local bytes and validation state; it does not endorse the source release.",
    }
    atomic_write_json(target / "manifest.json", manifest)
    return {"target": str(target), "manifest": manifest}


def load_imported_release(workspace: Path, version: str) -> dict[str, Any]:
    path = workspace / "observatory" / "releases" / version / "release.json"
    if not path.is_file():
        raise FileNotFoundError(f"Unknown observatory release {version}")
    return load_release(path)
