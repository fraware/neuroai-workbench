from __future__ import annotations

from pathlib import Path
from typing import Any

from ..util import atomic_write_json, canonical_json_bytes, sha256_bytes
from .adapters import adapt_inventory_entry
from .constants import (
    ACCESS_ACCESSIBLE,
    ACCESS_DIGEST_VERIFIED_EXTERNAL,
    BOUNDARY,
    DISPOSITION_ACCEPTED_WITH_RESIDUALS,
    DISPOSITION_PENDING,
    MIGRATION_BLOCKED,
    MIGRATION_DIGEST_RECORDED,
    MIGRATION_MIGRATED,
    MIGRATION_SKIPPED,
    RULESET_ID,
    SCHEMA_VERSION,
)
from .decisions import apply_warning_dispositions, decisions_by_subject, load_migration_decisions
from .inventory import load_archive_inventory, load_unresolved_ambiguities
from .ops_paths import resolve_ops_relpath


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
        "digest_recorded": 0,
        "material_warnings": 0,
    }
    for record in records:
        if record.get("governing"):
            summary["governing_records"] += 1
        access_state = record.get("access_state")
        if access_state in {ACCESS_ACCESSIBLE, ACCESS_DIGEST_VERIFIED_EXTERNAL}:
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
        elif state == MIGRATION_DIGEST_RECORDED:
            summary["digest_recorded"] += 1
        summary["material_warnings"] += len(record.get("material_warnings", []))
    return summary


def _v16_accessible_from_inventory(inventory: list[dict[str, Any]]) -> bool:
    for entry in inventory:
        if entry.get("family") != "OBSERVATORY_V1_6":
            continue
        ops_relpath = entry.get("ops_relpath")
        if isinstance(ops_relpath, str) and resolve_ops_relpath(ops_relpath) is not None:
            return True
        if entry.get("workbench_path"):
            return True
    return False


def _residuals_from_ambiguities(ambiguities: dict[str, Any]) -> list[str]:
    residuals: list[str] = []
    for item in ambiguities.get("ambiguities", []):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", ""))
        if status in {"INACCESSIBLE", "PENDING_ADMIN", "PENDING_REVIEW", "UNRESOLVED"}:
            ambiguity_id = item.get("ambiguity_id")
            if isinstance(ambiguity_id, str):
                residuals.append(ambiguity_id)
    return residuals


def build_migration_verification(
    repo_root: Path,
    *,
    inventory_path: Path | None = None,
    ambiguities_path: Path | None = None,
    decisions_path: Path | None = None,
    recorded_at: str,
) -> dict[str, Any]:
    inventory_path = inventory_path or repo_root / "migration/archive_inventory.jsonl"
    ambiguities_path = ambiguities_path or repo_root / "migration/unresolved_ambiguities.json"
    decisions_path = decisions_path or repo_root / "migration/MIGRATION_DECISIONS.jsonl"

    inventory = load_archive_inventory(inventory_path)
    ambiguities = load_unresolved_ambiguities(ambiguities_path)
    decisions = load_migration_decisions(decisions_path)
    by_subject = decisions_by_subject(decisions)
    predecessor_v16 = _v16_accessible_from_inventory(inventory)

    records = [
        adapt_inventory_entry(entry, repo_root, predecessor_v16_accessible=predecessor_v16) for entry in inventory
    ]
    for record in records:
        record["material_warnings"] = apply_warning_dispositions(record.get("material_warnings", []), by_subject)
        inv_decision = by_subject.get(str(record.get("inventory_id", "")))
        if inv_decision and isinstance(inv_decision.get("disposition"), str):
            record["human_disposition"] = inv_decision["disposition"]

    material_warnings = apply_warning_dispositions(_collect_material_warnings(records), by_subject)
    residuals = _residuals_from_ambiguities(ambiguities)
    top_decision = by_subject.get("MIGRATION_VERIFICATION")
    if top_decision and isinstance(top_decision.get("disposition"), str):
        human_disposition = top_decision["disposition"]
        if isinstance(top_decision.get("residuals"), list):
            residuals = [str(item) for item in top_decision["residuals"]]
    elif residuals:
        human_disposition = DISPOSITION_ACCEPTED_WITH_RESIDUALS
    else:
        human_disposition = DISPOSITION_PENDING

    verification_core = {
        "schema_version": SCHEMA_VERSION,
        "ruleset": RULESET_ID,
        "recorded_at": recorded_at,
        "boundary": BOUNDARY,
        "inventory_source": inventory_path.relative_to(repo_root).as_posix(),
        "ambiguities_source": ambiguities_path.relative_to(repo_root).as_posix(),
        "decisions_source": (
            decisions_path.relative_to(repo_root).as_posix() if decisions_path.is_file() else None
        ),
        "records": records,
        "material_warnings": material_warnings,
        "summary": _summary(records),
        "unresolved_ambiguities": ambiguities,
        "residuals": residuals,
        "human_disposition": human_disposition,
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
    decisions_path: Path | None = None,
    recorded_at: str,
) -> dict[str, Any]:
    document = build_migration_verification(
        repo_root,
        inventory_path=inventory_path,
        ambiguities_path=ambiguities_path,
        decisions_path=decisions_path,
        recorded_at=recorded_at,
    )
    atomic_write_json(output_path, document)
    return document
