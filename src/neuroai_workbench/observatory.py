from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .util import atomic_write_json, canonical_json_bytes, ensure_identifier, safe_join, sha256_bytes, sha256_file

_WINDOWS_RESERVED_NAME = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$",
    re.IGNORECASE,
)

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

FULL_RELEASE = "FULL_OBSERVATORY_RELEASE"
COMPACT_SUCCESSOR = "COMPACT_SUCCESSOR_SNAPSHOT"

KNOWN_REOPENING_DECISIONS = frozenset(
    {
        "NO_REOPENING_TRIGGER_IDENTIFIED",
        "UPDATE_REQUIRED_NO_ASSESSMENT_REOPEN",
        "METADATA_UPDATE_ONLY",
        "REOPEN_REQUIRED",
        "REOPENING_EXECUTED_RECORD_UPDATED_OPEN_CONDITIONS",
        "REOPENING_EXECUTED_CONDITIONS_CLOSED",
        "ASSESSMENT_REOPEN_DECLINED",
    }
)

ALLOWED_REOPENING_TRANSITIONS = frozenset(
    {
        ("REOPEN_REQUIRED", "REOPENING_EXECUTED_RECORD_UPDATED_OPEN_CONDITIONS"),
        ("REOPEN_REQUIRED", "REOPENING_EXECUTED_CONDITIONS_CLOSED"),
        ("REOPEN_REQUIRED", "ASSESSMENT_REOPEN_DECLINED"),
        ("REOPENING_EXECUTED_RECORD_UPDATED_OPEN_CONDITIONS", "REOPENING_EXECUTED_CONDITIONS_CLOSED"),
        ("NO_REOPENING_TRIGGER_IDENTIFIED", "REOPEN_REQUIRED"),
        ("UPDATE_REQUIRED_NO_ASSESSMENT_REOPEN", "REOPEN_REQUIRED"),
        ("METADATA_UPDATE_ONLY", "REOPEN_REQUIRED"),
    }
)


def load_release(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Observatory release must be a JSON object")
    return value


def release_kind(value: dict[str, Any]) -> str:
    if isinstance(value.get("successor_effective_counts"), dict) and isinstance(value.get("baseline_reference"), dict):
        return COMPACT_SUCCESSOR
    return FULL_RELEASE


def _ids(records: list[dict[str, Any]], field: str) -> list[str]:
    values: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        value = record.get(field)
        if isinstance(value, str):
            values.append(value)
    return values


def _parse_iso_date(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    candidate = value[:10]
    if len(candidate) == 10 and candidate[4] == "-" and candidate[7] == "-":
        return candidate
    return None


def verify_baseline_bytes(value: dict[str, Any], baseline_path: Path) -> list[dict[str, Any]]:
    """Verify compact-successor baseline_reference.canonical_sha256 against stored baseline bytes."""
    errors: list[dict[str, Any]] = []
    if release_kind(value) != COMPACT_SUCCESSOR:
        return errors
    baseline = value.get("baseline_reference", {})
    expected = baseline.get("canonical_sha256") if isinstance(baseline, dict) else None
    if not isinstance(expected, str) or len(expected) != 64:
        errors.append({"code": "BASELINE_SHA256_REQUIRED", "path": "baseline_reference.canonical_sha256"})
        return errors
    if not baseline_path.is_file():
        errors.append({"code": "BASELINE_BYTES_UNAVAILABLE", "path": str(baseline_path)})
        return errors
    observed = sha256_file(baseline_path)
    if observed != expected:
        errors.append(
            {
                "code": "BASELINE_SHA256_MISMATCH",
                "path": "baseline_reference.canonical_sha256",
                "expected": expected,
                "observed": observed,
            }
        )
    return errors


def _validate_full_release(value: dict[str, Any]) -> dict[str, Any]:
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
                    errors.append(
                        {
                            "code": "UNRESOLVED_SOURCE_REFERENCE",
                            "path": f"{key}[{index}].source_ids",
                            "source_id": source_id,
                        }
                    )

    organization_ids = {record["organization_id"] for record in value["organizations"] if record.get("organization_id")}
    for index, record in enumerate(value["organization_resolution"]):
        if record.get("organization_id") not in organization_ids:
            errors.append(
                {
                    "code": "UNRESOLVED_ORGANIZATION_REFERENCE",
                    "path": f"organization_resolution[{index}].organization_id",
                }
            )
    for index, record in enumerate(value["regional_expansion"]):
        if record.get("organization_id") not in organization_ids:
            errors.append(
                {"code": "UNRESOLVED_ORGANIZATION_REFERENCE", "path": f"regional_expansion[{index}].organization_id"}
            )

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
    }


def _validate_compact_successor(value: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    metadata = value.get("metadata")
    if not isinstance(metadata, dict):
        errors.append({"code": "METADATA_REQUIRED", "path": "metadata"})
        metadata = {}
    for field in ("title", "version", "effective_as_of", "status"):
        if not metadata.get(field):
            errors.append({"code": "METADATA_FIELD_REQUIRED", "path": f"metadata.{field}"})

    for field in (
        "baseline_reference",
        "baseline_counts",
        "delta_counts",
        "successor_effective_counts",
        "delta",
        "provenance",
    ):
        if not isinstance(value.get(field), dict):
            errors.append({"code": "OBJECT_REQUIRED", "path": field})
    if not isinstance(value.get("reopening_decisions"), list):
        errors.append({"code": "LIST_REQUIRED", "path": "reopening_decisions"})

    counts = (
        value.get("successor_effective_counts", {}) if isinstance(value.get("successor_effective_counts"), dict) else {}
    )
    for key, count in counts.items():
        if not isinstance(count, int) or count < 0:
            errors.append({"code": "NONNEGATIVE_INTEGER_REQUIRED", "path": f"successor_effective_counts.{key}"})

    baseline = value.get("baseline_reference", {})
    baseline_hash = baseline.get("canonical_sha256") if isinstance(baseline, dict) else None
    if not isinstance(baseline_hash, str) or len(baseline_hash) != 64:
        errors.append({"code": "BASELINE_SHA256_REQUIRED", "path": "baseline_reference.canonical_sha256"})
    if baseline.get("immutable") is not True:
        warnings.append({"code": "BASELINE_NOT_DECLARED_IMMUTABLE", "path": "baseline_reference.immutable"})

    decisions = value.get("reopening_decisions", []) if isinstance(value.get("reopening_decisions"), list) else []
    decision_ids: list[str] = []
    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            errors.append({"code": "OBJECT_REQUIRED", "path": f"reopening_decisions[{index}]"})
            continue
        decision_id = decision.get("decision_id")
        if not decision_id:
            errors.append({"code": "IDENTIFIER_REQUIRED", "path": f"reopening_decisions[{index}].decision_id"})
        else:
            decision_ids.append(decision_id)
        if not decision.get("object") or not decision.get("decision"):
            errors.append({"code": "DECISION_FIELDS_REQUIRED", "path": f"reopening_decisions[{index}]"})
        decision_state = decision.get("decision")
        if isinstance(decision_state, str) and decision_state not in KNOWN_REOPENING_DECISIONS:
            errors.append(
                {
                    "code": "UNSUPPORTED_REOPENING_STATE",
                    "path": f"reopening_decisions[{index}].decision",
                    "decision": decision_state,
                }
            )
    duplicates = sorted({item for item in decision_ids if decision_ids.count(item) > 1})
    if duplicates:
        errors.append({"code": "DUPLICATE_IDENTIFIER", "path": "reopening_decisions", "identifiers": duplicates})

    transition = None
    assessment_delta = value.get("assessment_successor_delta")
    if isinstance(assessment_delta, dict):
        transition = assessment_delta.get("reopening_transition")
    if isinstance(transition, dict):
        predecessor_state = transition.get("predecessor_state")
        successor_state = transition.get("successor_state")
        if predecessor_state and successor_state:
            pair = (predecessor_state, successor_state)
            if pair not in ALLOWED_REOPENING_TRANSITIONS and predecessor_state != successor_state:
                errors.append(
                    {
                        "code": "UNSUPPORTED_REOPENING_TRANSITION",
                        "path": "assessment_successor_delta.reopening_transition",
                        "predecessor_state": predecessor_state,
                        "successor_state": successor_state,
                    }
                )

    effective = _parse_iso_date(metadata.get("effective_as_of"))
    delta = value.get("delta", {}) if isinstance(value.get("delta"), dict) else {}
    event_dates: list[str] = []
    attributable_missing: list[str] = []
    for section, records in delta.items():
        if not isinstance(records, list):
            continue
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            event_date = _parse_iso_date(record.get("event_date"))
            if event_date:
                event_dates.append(event_date)
                if effective and event_date > effective:
                    errors.append(
                        {
                            "code": "INVALID_TEMPORAL_ORDER",
                            "path": f"delta.{section}[{index}].event_date",
                            "event_date": event_date,
                            "effective_as_of": effective,
                        }
                    )
            source_ids = record.get("source_ids")
            if not (isinstance(source_ids, list) and any(isinstance(item, str) and item for item in source_ids)):
                attributable_missing.append(f"delta.{section}[{index}]")
    if attributable_missing:
        warnings.append(
            {
                "code": "DELTA_ATTRIBUTABILITY_INCOMPLETE",
                "paths": attributable_missing,
                "detail": "Delta records should retain source_ids for attributability relative to the v1.6 refresh lineage.",
            }
        )

    predecessor = metadata.get("predecessor")
    predecessor_reference = value.get("predecessor_reference", {})
    if predecessor and not isinstance(predecessor_reference, dict):
        warnings.append({"code": "PREDECESSOR_REFERENCE_UNAVAILABLE"})
    elif isinstance(predecessor_reference, dict) and predecessor_reference.get("immutable") is not True:
        warnings.append({"code": "PREDECESSOR_NOT_DECLARED_IMMUTABLE", "path": "predecessor_reference.immutable"})

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": counts,
    }


def validate_release(value: dict[str, Any], *, baseline_path: Path | None = None) -> dict[str, Any]:
    kind = release_kind(value)
    core = _validate_compact_successor(value) if kind == COMPACT_SUCCESSOR else _validate_full_release(value)
    if kind == COMPACT_SUCCESSOR and baseline_path is not None:
        core["errors"].extend(verify_baseline_bytes(value, baseline_path))
        core["valid"] = not core["errors"]
    return {
        **core,
        "release_kind": kind,
        "canonical_sha256": sha256_bytes(canonical_json_bytes(value)),
        "boundary": "Mechanical validation does not establish scientific validity, authorization, deployment approval or system conformance.",
    }


def summarize_release(value: dict[str, Any]) -> dict[str, Any]:
    report = validate_release(value)
    if report["release_kind"] == COMPACT_SUCCESSOR:
        return {
            "metadata": value.get("metadata", {}),
            "valid": report["valid"],
            "release_kind": COMPACT_SUCCESSOR,
            "counts": report["counts"],
            "baseline_reference": value.get("baseline_reference", {}),
            "delta_counts": value.get("delta_counts", {}),
            "reopening_decision_states": {
                item.get("object"): item.get("decision")
                for item in value.get("reopening_decisions", [])
                if isinstance(item, dict)
            },
            "boundaries": [
                "A compact successor snapshot records changed state and lineage; it does not replace the detailed immutable baseline.",
                "Company announcements remain company evidence unless independently corroborated.",
                "Assessment, authorization, deployment and conformance states remain separate.",
            ],
        }

    coverage = value.get("coverage", {}).get("v1_4_effective_counts", {})
    exits = value.get("coverage", {}).get("exit_conditions", [])
    return {
        "metadata": value.get("metadata", {}),
        "valid": report["valid"],
        "release_kind": FULL_RELEASE,
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
    if release_kind(value) == COMPACT_SUCCESSOR:
        decisions = [
            {
                "decision_id": item.get("decision_id"),
                "object": item.get("object"),
                "decision": item.get("decision"),
                "required_actions": item.get("required_actions", []),
            }
            for item in value.get("reopening_decisions", [])
            if isinstance(item, dict)
            and item.get("decision") not in {"NO_REOPENING_TRIGGER_IDENTIFIED", "METADATA_UPDATE_ONLY"}
        ]
        return {
            "reopening_queue": decisions,
            "counts": {"reopening_decisions": len(decisions)},
            "boundary": "Queue inclusion records an open update or reassessment condition; it does not predetermine the resulting finding.",
        }

    org_queue = [
        {
            "organization_id": item.get("organization_id"),
            "name": item.get("canonical_name"),
            "verification_state": item.get("verification_state"),
        }
        for item in value.get("organizations", [])
        if item.get("verification_state")
        not in {
            "CURRENT_VERIFIED",
            "CURRENT_VERIFIED_RESCOPED",
            "CURRENT_VERIFIED_CORRECTED",
            "LEGACY_ONLY",
            "NON_ORGANIZATION_PROVENANCE_NODE",
            "HISTORICAL_ARCHIVED",
        }
    ]
    source_queue = [
        {
            "source_id": item.get("source_id"),
            "title": item.get("title"),
            "verification_state": item.get("verification_state"),
        }
        for item in value.get("sources", [])
        if item.get("verification_state") not in {"CURRENT_VERIFIED", "HISTORICAL_INPUT"}
    ]
    return {
        "organization_queue": org_queue,
        "source_queue": source_queue,
        "counts": {"organizations": len(org_queue), "sources": len(source_queue)},
        "boundary": "Queue closure requires evidence; unresolved records are not automatically downgraded or upgraded.",
    }


def _ensure_observatory_version(version: str) -> str:
    safe = ensure_identifier(str(version), "observatory version")
    if _WINDOWS_RESERVED_NAME.fullmatch(safe):
        raise ValueError(f"Invalid observatory version {version!r}; Windows reserved device names are refused.")
    return safe


def _release_store_path(workspace: Path, version: str) -> Path:
    safe_version = _ensure_observatory_version(version)
    return safe_join(workspace / "observatory" / "releases", safe_version) / "release.json"


def _resolve_baseline_path(workspace: Path, value: dict[str, Any]) -> Path | None:
    """Prefer an already-imported immutable baseline (v1.4) when verifying successors."""
    candidates = [
        _release_store_path(workspace, "v1.4"),
        workspace / "observatory" / "baseline" / "release.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def import_release(workspace: Path, release_path: Path) -> dict[str, Any]:
    value = load_release(release_path)
    baseline_path = _resolve_baseline_path(workspace, value) if release_kind(value) == COMPACT_SUCCESSOR else None
    report = validate_release(value, baseline_path=baseline_path)
    if not report["valid"]:
        raise ValueError("Observatory release failed validation")
    version = _ensure_observatory_version(str(value["metadata"]["version"]))
    target = safe_join(workspace / "observatory" / "releases", version)
    target.mkdir(parents=True, exist_ok=True)
    output = target / "release.json"
    if output.is_file():
        existing = load_release(output)
        existing_digest = sha256_bytes(canonical_json_bytes(existing))
        incoming_digest = sha256_bytes(canonical_json_bytes(value))
        if existing_digest != incoming_digest:
            raise ValueError(
                f"Refusing to overwrite observatory release {version!r}: historical snapshots are immutable. "
                "Import a distinct successor version instead of mutating stored bytes."
            )
        # Idempotent re-import of identical content is allowed.
    else:
        atomic_write_json(output, value)
    evidence_cutoff = value["metadata"].get("evidence_cutoff") or value["metadata"].get("effective_as_of")
    manifest = {
        "version": version,
        "release_kind": report["release_kind"],
        "evidence_cutoff": evidence_cutoff,
        "source_file": str(release_path),
        "source_sha256": sha256_file(release_path),
        "stored_sha256": sha256_file(output),
        "validation": report,
        "overwrite_prevented": True,
        "boundary": "Import records local bytes and validation state; it does not endorse the source release.",
    }
    atomic_write_json(target / "manifest.json", manifest)
    return {"target": str(target), "manifest": manifest}


def load_imported_release(workspace: Path, version: str) -> dict[str, Any]:
    path = _release_store_path(workspace, version)
    if not path.is_file():
        raise FileNotFoundError(f"Unknown observatory release {version}")
    return load_release(path)
