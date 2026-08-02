from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..monitoring import normalize_source_registry, validate_source_registry
from ..observatory import validate_release
from ..programme_adapter import PROGRAMME_FORMAT, detect_programme_assessment
from ..util import load_json, sha256_file
from ..validation import validate_assessment
from .constants import (
    ACCESS_ACCESSIBLE,
    ACCESS_INACCESSIBLE,
    ACCESS_NOT_RECORDED,
    ADAPTER_VERSION,
    DISPOSITION_PENDING,
    FAMILY_ADAPTER_IDS,
    FAMILY_ASSESSMENT_V4_2,
    FAMILY_EXTERNAL_ARCHIVE,
    FAMILY_OBSERVATORY_V1_4,
    FAMILY_OBSERVATORY_V1_6,
    FAMILY_OBSERVATORY_V1_7,
    FAMILY_POLICY,
    FAMILY_PROGRAMME_ADAPTER,
    FAMILY_SOURCE_REGISTRY,
    MIGRATION_BLOCKED,
    MIGRATION_MIGRATED,
    MIGRATION_SKIPPED,
)
from .digests import (
    assessment_v4_2_lineage,
    observatory_v1_4_lineage,
    observatory_v1_7_lineage,
    programme_adapter_lineage,
    source_registry_lineage,
    unknown_lineage_digest,
)


def _warning(
    warning_id: str,
    code: str,
    message: str,
    *,
    severity: str = "MATERIAL",
) -> dict[str, Any]:
    return {
        "warning_id": warning_id,
        "code": code,
        "severity": severity,
        "message": message,
        "human_disposition": DISPOSITION_PENDING,
    }


def _record_base(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "inventory_id": entry["inventory_id"],
        "family": entry["family"],
        "archive_key": entry["archive_key"],
        "workbench_path": entry.get("workbench_path"),
        "governing": bool(entry.get("governing")),
        "classification": entry.get("classification"),
        "store_target": entry.get("store_target"),
        "adapter_id": FAMILY_ADAPTER_IDS.get(entry["family"], "unknown-family-adapter"),
        "adapter_version": ADAPTER_VERSION,
        "material_warnings": [],
        "human_disposition": DISPOSITION_PENDING,
    }


def adapt_inaccessible(entry: dict[str, Any], *, reason: str) -> dict[str, Any]:
    record = _record_base(entry)
    sha_value = entry.get("sha256")
    if sha_value == "INACCESSIBLE":
        access_state = ACCESS_INACCESSIBLE
        source_sha256 = ACCESS_INACCESSIBLE
    else:
        access_state = ACCESS_NOT_RECORDED
        source_sha256 = ACCESS_NOT_RECORDED
    record.update(
        {
            "access_state": access_state,
            "source_sha256": source_sha256,
            "size_bytes": int(entry.get("size_bytes") or 0),
            "lineage_digest": unknown_lineage_digest(),
            "migration_state": MIGRATION_BLOCKED if entry.get("governing") else MIGRATION_SKIPPED,
            "validation": {"valid": False, "reason": reason},
        }
    )
    if entry.get("governing"):
        record["material_warnings"].append(
            _warning(
                f"WARN-{entry['inventory_id']}",
                "INACCESSIBLE_GOVERNING_OBJECT",
                reason,
            )
        )
    return record


def adapt_skipped(entry: dict[str, Any], *, reason: str) -> dict[str, Any]:
    record = _record_base(entry)
    workbench_path = entry.get("workbench_path")
    source_sha256 = entry.get("sha256", ACCESS_NOT_RECORDED)
    size_bytes = int(entry.get("size_bytes") or 0)
    if workbench_path and source_sha256 not in {ACCESS_INACCESSIBLE, ACCESS_NOT_RECORDED}:
        access_state = ACCESS_ACCESSIBLE
    elif entry.get("classification") == "INACCESSIBLE":
        access_state = ACCESS_INACCESSIBLE
    else:
        access_state = ACCESS_NOT_RECORDED
    record.update(
        {
            "access_state": access_state,
            "source_sha256": source_sha256,
            "size_bytes": size_bytes,
            "lineage_digest": unknown_lineage_digest(),
            "migration_state": MIGRATION_SKIPPED,
            "validation": {"valid": True, "reason": reason},
            "human_disposition": DISPOSITION_PENDING,
        }
    )
    return record


def adapt_observatory_v1_4(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    value = load_json(path)
    report = validate_release(value)
    source_sha256 = sha256_file(path)
    record = _record_base(entry)
    record.update(
        {
            "access_state": ACCESS_ACCESSIBLE,
            "source_sha256": source_sha256,
            "size_bytes": path.stat().st_size,
            "lineage_digest": observatory_v1_4_lineage(value, source_sha256),
            "migration_state": MIGRATION_MIGRATED,
            "validation": {
                "valid": report["valid"],
                "release_kind": report["release_kind"],
                "issue_count": len(report.get("errors", [])),
            },
            "human_disposition": DISPOSITION_PENDING,
        }
    )
    if not report["valid"]:
        record["material_warnings"].append(
            _warning(
                "WARN-OBS-V14-VALIDATION", "OBSERVATORY_VALIDATION", "Observatory v1.4 validation reported issues."
            )
        )
    return record


def adapt_observatory_v1_7(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    value = load_json(path)
    report = validate_release(value)
    source_sha256 = sha256_file(path)
    record = _record_base(entry)
    record.update(
        {
            "access_state": ACCESS_ACCESSIBLE,
            "source_sha256": source_sha256,
            "size_bytes": path.stat().st_size,
            "lineage_digest": observatory_v1_7_lineage(value, source_sha256),
            "migration_state": MIGRATION_MIGRATED,
            "validation": {
                "valid": report["valid"],
                "release_kind": report["release_kind"],
                "issue_count": len(report.get("errors", [])),
            },
            "human_disposition": DISPOSITION_PENDING,
        }
    )
    record["material_warnings"].append(
        _warning(
            "WARN-OBS-V17-PREDECESSOR",
            "INACCESSIBLE_PREDECESSOR_DELTA",
            "Successor snapshot references predecessor v1.6; governing v1.6 delta bytes remain INACCESSIBLE.",
        )
    )
    if not report["valid"]:
        record["material_warnings"].append(
            _warning(
                "WARN-OBS-V17-VALIDATION", "OBSERVATORY_VALIDATION", "Observatory v1.7 validation reported issues."
            )
        )
    return record


def adapt_assessment_v4_2(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    value = load_json(path)
    report = validate_assessment(value)
    source_sha256 = sha256_file(path)
    metadata = value.get("assessment_metadata", {})
    record = _record_base(entry)
    record.update(
        {
            "access_state": ACCESS_ACCESSIBLE,
            "source_sha256": source_sha256,
            "size_bytes": path.stat().st_size,
            "lineage_digest": assessment_v4_2_lineage(value, source_sha256),
            "migration_state": MIGRATION_MIGRATED,
            "validation": {
                "valid": report.valid,
                "assessment_id": metadata.get("assessment_id"),
                "instrument_version": metadata.get("instrument_version"),
                "issue_count": len(report.schema_issues) + len(report.semantic_issues),
            },
            "human_disposition": DISPOSITION_PENDING,
        }
    )
    if not report.valid:
        record["material_warnings"].append(
            _warning("WARN-ASM-VALIDATION", "ASSESSMENT_VALIDATION", "Assessment validation reported issues.")
        )
    return record


def adapt_source_registry(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    registry = normalize_source_registry(raw)
    validation = validate_source_registry(registry)
    source_sha256 = sha256_file(path)
    record = _record_base(entry)
    record.update(
        {
            "access_state": ACCESS_ACCESSIBLE,
            "source_sha256": source_sha256,
            "size_bytes": path.stat().st_size,
            "lineage_digest": source_registry_lineage(registry, source_sha256),
            "migration_state": MIGRATION_MIGRATED,
            "validation": {
                "valid": validation["valid"],
                "record_count": validation.get("counts", {}).get("sources"),
                "warning_count": len(validation.get("warnings", [])),
            },
            "human_disposition": DISPOSITION_PENDING,
        }
    )
    record["material_warnings"].append(
        _warning(
            "WARN-REG-SAMPLE-ONLY",
            "INACCESSIBLE_FULL_REGISTRY",
            "Only the synthetic SOURCE_MONITOR_REGISTRY sample is present; full v1.5 registry bytes remain INACCESSIBLE.",
        )
    )
    return record


def adapt_programme_adapter(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    value = load_json(path)
    if not detect_programme_assessment(value):
        raise ValueError(f"{path} is not a programme completed-assessment input")
    source_sha256 = sha256_file(path)
    metadata = value.get("metadata", {})
    record = _record_base(entry)
    record.update(
        {
            "access_state": ACCESS_ACCESSIBLE,
            "source_sha256": source_sha256,
            "size_bytes": path.stat().st_size,
            "lineage_digest": programme_adapter_lineage(value, source_sha256),
            "migration_state": MIGRATION_MIGRATED,
            "validation": {
                "valid": True,
                "format": PROGRAMME_FORMAT,
                "assessment_id": metadata.get("assessment_id"),
            },
            "human_disposition": DISPOSITION_PENDING,
        }
    )
    return record


def adapt_inventory_entry(entry: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    family = entry.get("family")
    classification = entry.get("classification")
    sha_value = entry.get("sha256")
    workbench_path = entry.get("workbench_path")

    if classification in {"INACCESSIBLE", "UNRESOLVED"} or sha_value == "INACCESSIBLE":
        return adapt_inaccessible(entry, reason=entry.get("notes", "External archive object is INACCESSIBLE."))

    if not entry.get("governing"):
        return adapt_skipped(entry, reason="Non-governing inventory object recorded but not migrated.")

    if not workbench_path:
        return adapt_inaccessible(entry, reason="Governing object has no workbench path and no accessible bytes.")

    path = repo_root / workbench_path
    if not path.is_file():
        return adapt_inaccessible(entry, reason=f"Expected fixture missing at {workbench_path}.")

    if family == FAMILY_OBSERVATORY_V1_4:
        return adapt_observatory_v1_4(path, entry)
    if family == FAMILY_OBSERVATORY_V1_7:
        return adapt_observatory_v1_7(path, entry)
    if family == FAMILY_ASSESSMENT_V4_2:
        return adapt_assessment_v4_2(path, entry)
    if family == FAMILY_SOURCE_REGISTRY:
        return adapt_source_registry(path, entry)
    if family == FAMILY_PROGRAMME_ADAPTER:
        return adapt_programme_adapter(path, entry)
    if family in {FAMILY_OBSERVATORY_V1_6, FAMILY_EXTERNAL_ARCHIVE, FAMILY_POLICY}:
        return adapt_inaccessible(entry, reason=f"No adapter for family {family} with accessible bytes.")

    raise ValueError(f"Unsupported inventory family: {family}")
