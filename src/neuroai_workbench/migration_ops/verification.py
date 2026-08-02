from __future__ import annotations

from pathlib import Path
from typing import Any

from ..util import atomic_write_json, canonical_json_bytes, sha256_bytes
from .adapters import adapt_inventory_entry
from .constants import (
    BOUNDARY,
    DISPOSITION_PENDING,
    MIGRATION_BLOCKED,
    MIGRATION_MIGRATED,
    MIGRATION_SKIPPED,
    RULESET_ID,
    SCHEMA_VERSION,
)
from .inventory import load_archive_inventory, load_unresolved_ambiguities


def _collect_material_warnings(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        for warning in record.get("material_warnings", []):
            warning_id = warning["warning_id"]
            if warning_id in seen:
                continue
            seen.add(warning_id)
            warnings.append(warning)
    return warnings


def _summary(records: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "inventory_records": len(records),
        "governing_records": 0,
        "accessible": 0,
        "inaccessible": 0,
        "migrated": 0,
        "blocked": 0,
        "skipped": 0,
        "material_warnings": 0,
    }
    for record in records:
        if record.get("governing"):
            summary["governing_records"] += 1
        access_state = record.get("access_state")
        if access_state == "ACCESSIBLE":
            summary["accessible"] += 1
        if access_state in {"INACCESSIBLE", "NOT_RECORDED", "UNKNOWN"}:
            summary["inaccessible"] += 1
        state = record.get("migration_state")
        if state == MIGRATION_MIGRATED:
            summary["migrated"] += 1
        elif state == MIGRATION_BLOCKED:
            summary["blocked"] += 1
        elif state == MIGRATION_SKIPPED:
            summary["skipped"] += 1
        summary["material_warnings"] += len(record.get("material_warnings", []))
    return summary


def build_migration_verification(
    repo_root: Path,
    *,
    inventory_path: Path | None = None,
    ambiguities_path: Path | None = None,
    recorded_at: str,
) -> dict[str, Any]:
    inventory_path = inventory_path or repo_root / "migration/archive_inventory.jsonl"
    ambiguities_path = ambiguities_path or repo_root / "migration/unresolved_ambiguities.json"

    inventory = load_archive_inventory(inventory_path)
    ambiguities = load_unresolved_ambiguities(ambiguities_path)
    records = [adapt_inventory_entry(entry, repo_root) for entry in inventory]
    material_warnings = _collect_material_warnings(records)

    verification_core = {
        "schema_version": SCHEMA_VERSION,
        "ruleset": RULESET_ID,
        "recorded_at": recorded_at,
        "boundary": BOUNDARY,
        "inventory_source": inventory_path.relative_to(repo_root).as_posix(),
        "ambiguities_source": ambiguities_path.relative_to(repo_root).as_posix(),
        "records": records,
        "material_warnings": material_warnings,
        "summary": _summary(records),
        "unresolved_ambiguities": ambiguities,
        "human_disposition": DISPOSITION_PENDING,
    }
    verification_digest = sha256_bytes(canonical_json_bytes(verification_core))
    return {
        **verification_core,
        "verification_id": f"MIG-VERIFY-{verification_digest[:12].upper()}",
        "verification_digest": verification_digest,
    }


def write_migration_verification(
    repo_root: Path,
    output_path: Path,
    *,
    inventory_path: Path | None = None,
    ambiguities_path: Path | None = None,
    recorded_at: str,
) -> dict[str, Any]:
    document = build_migration_verification(
        repo_root,
        inventory_path=inventory_path,
        ambiguities_path=ambiguities_path,
        recorded_at=recorded_at,
    )
    atomic_write_json(output_path, document)
    return document
