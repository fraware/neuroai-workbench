"""Governed preservation for predecessor identity and coverage history.

These v1.4 families are authoritative predecessor history but do not map cleanly to
ordinary v2 graph objects without flattening semantics. They therefore remain
content-addressed migration sidecars with exact organization/source bindings.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .observatory_migration import predecessor_time_value
from .util import canonical_json_bytes, sha256_bytes

HISTORY_MIGRATION_BOUNDARY = (
    "Predecessor identity-resolution and regional-expansion history only. Records remain exact, "
    "content-addressed migration state and are not promoted to native graph Events, Assertions, or "
    "Relationships. Preservation does not confer substantive truth, currentness, or publication authority."
)

IDENTITY_RESOLUTION_STATE = "PRESERVED_IDENTITY_RESOLUTION_HISTORY"
REGIONAL_EXPANSION_STATE = "PRESERVED_REGIONAL_EXPANSION_HISTORY"

_RESOLUTION_FIELDS = frozenset(
    {
        "resolution_id",
        "organization_id",
        "name_before",
        "verification_before",
        "disposition",
        "verification_after",
        "source_ids",
        "rationale",
        "effective_date",
    }
)
_REGIONAL_FIELDS = frozenset(
    {
        "regional_record_id",
        "organization_id",
        "canonical_name",
        "unesco_region",
        "country_or_scope",
        "action",
        "inclusion_rule",
        "verification_state",
        "source_ids",
        "claim_boundary",
    }
)


class ObservatoryHistoryMigrationError(ValueError):
    """Raised when predecessor history cannot be preserved with exact bindings."""


def _digest(record: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(record))


def _require_exact_fields(record: dict[str, Any], expected: frozenset[str], *, family: str) -> None:
    actual = set(record)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise ObservatoryHistoryMigrationError(f"{family} predecessor shape mismatch: missing={missing}, extra={extra}")


def _require_string(record: dict[str, Any], field: str, *, family: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ObservatoryHistoryMigrationError(f"{family}.{field} must be a non-empty string")
    return value.strip()


def _require_source_ids(value: Any, known_source_ids: set[str], *, family: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ObservatoryHistoryMigrationError(f"{family}.source_ids must be an array of non-empty strings")
    missing = sorted(set(value) - known_source_ids)
    if missing:
        raise ObservatoryHistoryMigrationError(f"{family} references missing Sources {missing}")
    return list(value)


def preserve_v14_organization_resolution_history(
    v14_release: dict[str, Any],
    *,
    organization_records: dict[str, dict[str, Any]],
    known_source_ids: set[str],
) -> dict[str, Any]:
    """Preserve all v1.4 organization-resolution decisions with after-state reconciliation."""
    records = v14_release.get("organization_resolution")
    if not isinstance(records, list):
        raise ObservatoryHistoryMigrationError("Expected v1.4 organization_resolution array")

    preserved: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    disposition_counts: Counter[str] = Counter()
    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            raise ObservatoryHistoryMigrationError(f"organization_resolution record {index} must be an object")
        _require_exact_fields(raw, _RESOLUTION_FIELDS, family="organization_resolution")
        resolution_id = _require_string(raw, "resolution_id", family="organization_resolution")
        if resolution_id in seen_ids:
            raise ObservatoryHistoryMigrationError(f"duplicate resolution_id {resolution_id}")
        seen_ids.add(resolution_id)

        organization_id = _require_string(raw, "organization_id", family="organization_resolution")
        organization = organization_records.get(organization_id)
        if organization is None:
            raise ObservatoryHistoryMigrationError(
                f"organization_resolution references unknown predecessor organization {organization_id}"
            )
        name_before = _require_string(raw, "name_before", family="organization_resolution")
        if organization.get("canonical_name") != name_before:
            raise ObservatoryHistoryMigrationError(
                f"organization_resolution {resolution_id} name_before does not match predecessor organization"
            )
        verification_after = _require_string(raw, "verification_after", family="organization_resolution")
        if organization.get("verification_state") != verification_after:
            raise ObservatoryHistoryMigrationError(
                f"organization_resolution {resolution_id} verification_after does not match resulting organization state"
            )
        _require_string(raw, "verification_before", family="organization_resolution")
        disposition = _require_string(raw, "disposition", family="organization_resolution")
        _require_string(raw, "rationale", family="organization_resolution")
        source_ids = _require_source_ids(raw.get("source_ids"), known_source_ids, family="organization_resolution")
        effective = predecessor_time_value(raw.get("effective_date"))
        if effective is None:
            raise ObservatoryHistoryMigrationError(
                f"organization_resolution {resolution_id} requires explicit effective_date"
            )
        disposition_counts[disposition] += 1
        preserved.append(
            {
                "migration_state": IDENTITY_RESOLUTION_STATE,
                "role": "V14",
                "family": "organization_resolution",
                "record_index": index,
                "record_id": resolution_id,
                "organization_id": organization_id,
                "effective_at": effective,
                "source_ids": source_ids,
                "predecessor_record_sha256": _digest(raw),
                "predecessor_record": raw,
                "native_object_created": False,
                "native_authority": False,
                "boundary": HISTORY_MIGRATION_BOUNDARY,
            }
        )

    return {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "migration_state": IDENTITY_RESOLUTION_STATE,
        "input_record_count": len(records),
        "preserved_record_count": len(preserved),
        "native_object_count": 0,
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "records": preserved,
        "boundary": HISTORY_MIGRATION_BOUNDARY,
    }


def preserve_v14_regional_expansion_history(
    v14_release: dict[str, Any],
    *,
    organization_records: dict[str, dict[str, Any]],
    materialized_entity_ids: set[str],
    known_source_ids: set[str],
) -> dict[str, Any]:
    """Preserve regional acquisition history without overwriting contemporaneous verification state."""
    records = v14_release.get("regional_expansion")
    if not isinstance(records, list):
        raise ObservatoryHistoryMigrationError("Expected v1.4 regional_expansion array")

    preserved: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    action_counts: Counter[str] = Counter()
    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            raise ObservatoryHistoryMigrationError(f"regional_expansion record {index} must be an object")
        _require_exact_fields(raw, _REGIONAL_FIELDS, family="regional_expansion")
        record_id = _require_string(raw, "regional_record_id", family="regional_expansion")
        if record_id in seen_ids:
            raise ObservatoryHistoryMigrationError(f"duplicate regional_record_id {record_id}")
        seen_ids.add(record_id)
        organization_id = _require_string(raw, "organization_id", family="regional_expansion")
        organization = organization_records.get(organization_id)
        if organization is None:
            raise ObservatoryHistoryMigrationError(
                f"regional_expansion references unknown predecessor organization {organization_id}"
            )
        if organization_id not in materialized_entity_ids:
            raise ObservatoryHistoryMigrationError(
                f"regional_expansion organization {organization_id} is not an identity-safe materialized Entity"
            )
        canonical_name = _require_string(raw, "canonical_name", family="regional_expansion")
        if organization.get("canonical_name") != canonical_name:
            raise ObservatoryHistoryMigrationError(
                f"regional_expansion {record_id} canonical_name does not match predecessor organization"
            )
        action = _require_string(raw, "action", family="regional_expansion")
        _require_string(raw, "unesco_region", family="regional_expansion")
        _require_string(raw, "country_or_scope", family="regional_expansion")
        _require_string(raw, "inclusion_rule", family="regional_expansion")
        verification_state = _require_string(raw, "verification_state", family="regional_expansion")
        _require_string(raw, "claim_boundary", family="regional_expansion")
        source_ids = _require_source_ids(raw.get("source_ids"), known_source_ids, family="regional_expansion")
        action_counts[action] += 1
        preserved.append(
            {
                "migration_state": REGIONAL_EXPANSION_STATE,
                "role": "V14",
                "family": "regional_expansion",
                "record_index": index,
                "record_id": record_id,
                "organization_id": organization_id,
                "contemporaneous_verification_state": verification_state,
                "source_ids": source_ids,
                "predecessor_record_sha256": _digest(raw),
                "predecessor_record": raw,
                "native_object_created": False,
                "native_authority": False,
                "boundary": HISTORY_MIGRATION_BOUNDARY,
            }
        )

    return {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "migration_state": REGIONAL_EXPANSION_STATE,
        "input_record_count": len(records),
        "preserved_record_count": len(preserved),
        "native_object_count": 0,
        "action_counts": dict(sorted(action_counts.items())),
        "records": preserved,
        "boundary": HISTORY_MIGRATION_BOUNDARY,
    }


def verify_preserved_history_record(record: dict[str, Any]) -> list[str]:
    """Verify one preserved history record without relying on generator state."""
    errors: list[str] = []
    predecessor = record.get("predecessor_record")
    if not isinstance(predecessor, dict):
        return ["predecessor_record must be an object"]
    if record.get("predecessor_record_sha256") != _digest(predecessor):
        errors.append("predecessor_record_sha256 mismatch")
    if record.get("native_object_created") is not False:
        errors.append("native_object_created must remain false")
    if record.get("native_authority") is not False:
        errors.append("native_authority must remain false")
    if record.get("boundary") != HISTORY_MIGRATION_BOUNDARY:
        errors.append("history migration boundary mismatch")
    family = record.get("family")
    expected_state = {
        "organization_resolution": IDENTITY_RESOLUTION_STATE,
        "regional_expansion": REGIONAL_EXPANSION_STATE,
    }.get(family)
    if expected_state is None:
        errors.append(f"unsupported history family {family!r}")
    elif record.get("migration_state") != expected_state:
        errors.append("history migration_state mismatch")
    return sorted(set(errors))
