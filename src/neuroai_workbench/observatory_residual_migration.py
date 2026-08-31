"""Governed preservation for residual Gate-A predecessor families and registries.

The first Observatory-v2 milestone is representational: predecessor semantics that do
not yet have safe native graph mappings remain exact, content-addressed migration
payloads with explicit blocker reasons. This module also proves the standalone v1.4
Source Register duplicates the canonical v1.4 source array and that the v1.5 monitor
registry is a one-to-one operational projection over those source identities.
"""

from __future__ import annotations

from typing import Any

from .util import canonical_json_bytes, sha256_bytes

RESIDUAL_MIGRATION_BOUNDARY = (
    "Explicitly retained predecessor payload for first-v2 lossless representation. Residual model, registry, "
    "relationship, quality, delta, release-level, and monitoring semantics remain exact migration state until "
    "a governed native representation exists. Preservation is not substantive truth or publication authority."
)
RESIDUAL_STATE = "PRESERVED_GOVERNED_LEGACY_FAMILY"
RELEASE_LEVEL_STATE = "PRESERVED_RELEASE_LEVEL_STATE"
SOURCE_REGISTER_DUPLICATE_STATE = "VERIFIED_DUPLICATE_SOURCE_REGISTER"
MONITOR_REGISTRY_STATE = "PRESERVED_OPERATIONAL_MONITOR_REGISTRY"

RESIDUAL_POLICIES: dict[tuple[str, str], str] = {
    ("V14", "representative_model_records"): "MODEL_IDENTITY_LEVEL_UNRESOLVED",
    ("V14", "model_and_dataset_registry"): "AGGREGATE_REGISTRY_SEMANTICS",
    ("V14", "trial_site_relationships"): "ENDPOINT_IDENTITY_UNRESOLVED",
    ("V14", "participant_authority_relationships"): "ENDPOINT_IDENTITY_AND_PRIVACY_SCOPE_UNRESOLVED",
    ("V14", "supplier_dependency_relationships"): "ENDPOINT_IDENTITY_UNRESOLVED",
    ("V14", "data_quality"): "RELEASE_LEVEL_QUALITY_STATE",
    ("DELTA16", "regulatory_and_market_events"): "SYSTEM_IDENTITY_UNRESOLVED",
    ("DELTA16", "capital_and_ownership_events"): "NATIVE_EVIDENCE_SEMANTICS_UNRESOLVED",
    ("DELTA16", "model_records"): "MODEL_IDENTITY_LEVEL_UNRESOLVED",
    ("DELTA16", "supplier_dependency_relationships"): "ENDPOINT_IDENTITY_UNRESOLVED",
    ("DELTA16", "governance_and_leadership_events"): "EVENT_SEMANTICS_REQUIRES_GOVERNED_MAPPING",
}


class ObservatoryResidualMigrationError(ValueError):
    """Raised when a residual predecessor family cannot be preserved exactly."""


def _digest(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _validate_source_refs(value: Any, known_source_ids: set[str], *, path: str = "$") -> list[str]:
    """Return missing source ids found recursively in explicit source_id/source_ids fields."""
    missing: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "source_id" and isinstance(item, str) and item not in known_source_ids:
                missing.add(item)
            elif key == "source_ids":
                if not isinstance(item, list) or any(not isinstance(source_id, str) or not source_id for source_id in item):
                    raise ObservatoryResidualMigrationError(f"{path}.source_ids must be an array of non-empty strings")
                missing.update(source_id for source_id in item if source_id not in known_source_ids)
            else:
                missing.update(_validate_source_refs(item, known_source_ids, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            missing.update(_validate_source_refs(item, known_source_ids, path=f"{path}[{index}]"))
    return sorted(missing)


def _preserve_family(
    *,
    role: str,
    family: str,
    payload: Any,
    known_source_ids: set[str],
) -> dict[str, Any]:
    reason = RESIDUAL_POLICIES.get((role, family))
    if reason is None:
        raise ObservatoryResidualMigrationError(f"no governed residual policy for {role}.{family}")
    if not isinstance(payload, list):
        raise ObservatoryResidualMigrationError(f"{role}.{family} must be an array")
    if any(not isinstance(record, dict) for record in payload):
        raise ObservatoryResidualMigrationError(f"{role}.{family} entries must be objects")
    missing_sources = _validate_source_refs(payload, known_source_ids, path=f"{role}.{family}")
    if missing_sources:
        raise ObservatoryResidualMigrationError(
            f"{role}.{family} references missing Sources {missing_sources}"
        )
    return {
        "migration_state": RESIDUAL_STATE,
        "role": role,
        "family": family,
        "blocked_reason": reason,
        "record_count": len(payload),
        "payload_sha256": _digest(payload),
        "payload": payload,
        "native_object_count": 0,
        "native_authority": False,
        "boundary": RESIDUAL_MIGRATION_BOUNDARY,
    }


def preserve_residual_gate_a_state(
    *,
    v14_release: dict[str, Any],
    v16_refresh: dict[str, Any],
    delta16: dict[str, Any],
    source_register14: list[dict[str, Any]],
    monitor15: list[dict[str, Any]],
    known_source_ids: set[str],
) -> dict[str, Any]:
    """Preserve all currently non-native residual families and prove registry identities."""
    v14_sources = v14_release.get("sources")
    if not isinstance(v14_sources, list) or any(not isinstance(item, dict) for item in v14_sources):
        raise ObservatoryResidualMigrationError("v1.4 sources must be an array of objects")
    if source_register14 != v14_sources:
        raise ObservatoryResidualMigrationError(
            "standalone v1.4 Source Register is not exactly the canonical v1.4 sources array"
        )

    source_by_id = {
        str(record.get("source_id")): record
        for record in v14_sources
        if isinstance(record.get("source_id"), str)
    }
    if len(source_by_id) != len(v14_sources):
        raise ObservatoryResidualMigrationError("v1.4 source ids must be complete and unique")
    if not isinstance(monitor15, list) or any(not isinstance(item, dict) for item in monitor15):
        raise ObservatoryResidualMigrationError("v1.5 monitor registry must be an array of objects")
    monitor_ids: set[str] = set()
    monitored_source_ids: set[str] = set()
    expected_monitor_fields = {
        "url": "url",
        "publisher": "publisher",
        "source_class": "source_class",
        "baseline_evidence_state": "evidence_state",
        "baseline_verification_state": "verification_state",
        "baseline_claim_boundary": "claim_boundary",
        "last_successful_retrieval": "retrieved",
    }
    for index, monitor in enumerate(monitor15):
        monitor_id = monitor.get("monitor_id")
        source_id = monitor.get("source_id")
        if not isinstance(monitor_id, str) or not monitor_id:
            raise ObservatoryResidualMigrationError(f"monitor record {index} lacks monitor_id")
        if not isinstance(source_id, str) or not source_id:
            raise ObservatoryResidualMigrationError(f"monitor record {index} lacks source_id")
        if monitor_id in monitor_ids:
            raise ObservatoryResidualMigrationError(f"duplicate monitor_id {monitor_id}")
        if source_id in monitored_source_ids:
            raise ObservatoryResidualMigrationError(f"duplicate monitored source_id {source_id}")
        monitor_ids.add(monitor_id)
        monitored_source_ids.add(source_id)
        source = source_by_id.get(source_id)
        if source is None:
            raise ObservatoryResidualMigrationError(f"monitor {monitor_id} references unknown v1.4 Source {source_id}")
        for monitor_field, source_field in expected_monitor_fields.items():
            if monitor.get(monitor_field) != source.get(source_field):
                raise ObservatoryResidualMigrationError(
                    f"monitor {monitor_id} {monitor_field} does not match predecessor Source.{source_field}"
                )
    if monitored_source_ids != set(source_by_id):
        missing = sorted(set(source_by_id) - monitored_source_ids)
        extra = sorted(monitored_source_ids - set(source_by_id))
        raise ObservatoryResidualMigrationError(
            f"v1.5 monitor registry is not one-to-one over v1.4 Sources: missing={missing}, extra={extra}"
        )

    families: list[dict[str, Any]] = []
    for role, source, family_names in (
        (
            "V14",
            v14_release,
            (
                "representative_model_records",
                "model_and_dataset_registry",
                "trial_site_relationships",
                "participant_authority_relationships",
                "supplier_dependency_relationships",
                "data_quality",
            ),
        ),
        (
            "DELTA16",
            delta16,
            (
                "regulatory_and_market_events",
                "capital_and_ownership_events",
                "model_records",
                "supplier_dependency_relationships",
                "governance_and_leadership_events",
            ),
        ),
    ):
        for family in family_names:
            if family not in source:
                raise ObservatoryResidualMigrationError(f"required residual family {role}.{family} is missing")
            families.append(
                _preserve_family(
                    role=role,
                    family=family,
                    payload=source[family],
                    known_source_ids=known_source_ids,
                )
            )

    release_level = [
        {
            "migration_state": RELEASE_LEVEL_STATE,
            "role": "V14",
            "families": ["metadata", "methodology", "coverage"],
            "payload": {
                "metadata": v14_release.get("metadata"),
                "methodology": v14_release.get("methodology"),
                "coverage": v14_release.get("coverage"),
            },
            "native_object_count": 0,
            "native_authority": False,
            "boundary": RESIDUAL_MIGRATION_BOUNDARY,
        },
        {
            "migration_state": RELEASE_LEVEL_STATE,
            "role": "V16",
            "families": ["metadata", "methodology", "baseline"],
            "payload": {
                "metadata": v16_refresh.get("metadata"),
                "methodology": v16_refresh.get("methodology"),
                "baseline": v16_refresh.get("baseline"),
            },
            "native_object_count": 0,
            "native_authority": False,
            "boundary": RESIDUAL_MIGRATION_BOUNDARY,
        },
    ]
    for item in release_level:
        item["payload_sha256"] = _digest(item["payload"])

    state = {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "native_object_count": 0,
        "residual_families": families,
        "release_level_state": release_level,
        "source_register_proof": {
            "migration_state": SOURCE_REGISTER_DUPLICATE_STATE,
            "record_count": len(source_register14),
            "source_register_sha256": _digest(source_register14),
            "v14_sources_sha256": _digest(v14_sources),
            "exact_duplicate": True,
            "native_object_count": 0,
            "native_authority": False,
            "boundary": RESIDUAL_MIGRATION_BOUNDARY,
        },
        "monitor_registry": {
            "migration_state": MONITOR_REGISTRY_STATE,
            "record_count": len(monitor15),
            "one_to_one_source_identity": True,
            "monitor_registry_sha256": _digest(monitor15),
            "payload": monitor15,
            "native_object_count": 0,
            "native_authority": False,
            "boundary": RESIDUAL_MIGRATION_BOUNDARY,
        },
        "counts": {
            "residual_family_count": len(families),
            "residual_record_count": sum(item["record_count"] for item in families),
            "release_level_bundle_count": len(release_level),
            "source_register_records": len(source_register14),
            "monitor_registry_records": len(monitor15),
        },
        "boundary": RESIDUAL_MIGRATION_BOUNDARY,
    }
    errors = verify_residual_gate_a_state(state, known_source_ids=known_source_ids)
    if errors:
        raise ObservatoryResidualMigrationError(f"generated residual migration state is invalid: {errors}")
    return state


def verify_residual_gate_a_state(
    state: dict[str, Any],
    *,
    known_source_ids: set[str],
) -> list[str]:
    """Verify digests, policies, source references, and nonnative authority boundary."""
    errors: list[str] = []
    if state.get("state") != "NONCANONICAL_CANDIDATE" or state.get("release_authorized") is not False:
        errors.append("residual migration state must remain noncanonical and unauthorized")
    if state.get("native_object_count") != 0:
        errors.append("residual migration must not claim native objects")
    if state.get("boundary") != RESIDUAL_MIGRATION_BOUNDARY:
        errors.append("residual migration boundary mismatch")

    families = state.get("residual_families")
    if not isinstance(families, list):
        return ["residual_families must be an array"]
    for item in families:
        if not isinstance(item, dict):
            errors.append("residual family entry must be an object")
            continue
        key = (item.get("role"), item.get("family"))
        expected_reason = RESIDUAL_POLICIES.get(key)
        if expected_reason is None or item.get("blocked_reason") != expected_reason:
            errors.append(f"residual family policy mismatch for {key}")
        payload = item.get("payload")
        if item.get("payload_sha256") != _digest(payload):
            errors.append(f"residual family digest mismatch for {key}")
        if not isinstance(payload, list) or item.get("record_count") != len(payload):
            errors.append(f"residual family record count mismatch for {key}")
        missing = _validate_source_refs(payload, known_source_ids, path=f"{key}")
        if missing:
            errors.append(f"residual family {key} references missing Sources {missing}")
        if item.get("native_object_count") != 0 or item.get("native_authority") is not False:
            errors.append(f"residual family {key} must remain nonnative and unauthorized")

    release_level = state.get("release_level_state")
    if not isinstance(release_level, list):
        errors.append("release_level_state must be an array")
        release_level = []
    for item in release_level:
        if not isinstance(item, dict):
            errors.append("release-level migration entry must be an object")
            continue
        if item.get("migration_state") != RELEASE_LEVEL_STATE:
            errors.append("release-level migration_state mismatch")
        if item.get("payload_sha256") != _digest(item.get("payload")):
            errors.append("release-level payload digest mismatch")
        if item.get("native_object_count") != 0 or item.get("native_authority") is not False:
            errors.append("release-level state must remain nonnative and unauthorized")

    source_register = state.get("source_register_proof")
    if not isinstance(source_register, dict):
        errors.append("source_register_proof missing")
    else:
        if source_register.get("migration_state") != SOURCE_REGISTER_DUPLICATE_STATE:
            errors.append("source-register migration_state mismatch")
        if source_register.get("exact_duplicate") is not True:
            errors.append("source-register exact-duplicate proof failed")
        if source_register.get("source_register_sha256") != source_register.get("v14_sources_sha256"):
            errors.append("source-register/v1.4 source digest mismatch")

    monitor = state.get("monitor_registry")
    if not isinstance(monitor, dict):
        errors.append("monitor_registry missing")
    else:
        if monitor.get("migration_state") != MONITOR_REGISTRY_STATE:
            errors.append("monitor-registry migration_state mismatch")
        if monitor.get("one_to_one_source_identity") is not True:
            errors.append("monitor registry must remain one-to-one over source identities")
        if monitor.get("monitor_registry_sha256") != _digest(monitor.get("payload")):
            errors.append("monitor-registry payload digest mismatch")
        if monitor.get("native_object_count") != 0 or monitor.get("native_authority") is not False:
            errors.append("monitor registry must remain nonnative and unauthorized")

    expected_counts = {
        "residual_family_count": len(families),
        "residual_record_count": sum(
            int(item.get("record_count", 0)) for item in families if isinstance(item, dict)
        ),
        "release_level_bundle_count": len(release_level),
        "source_register_records": int(source_register.get("record_count", 0)) if isinstance(source_register, dict) else 0,
        "monitor_registry_records": int(monitor.get("record_count", 0)) if isinstance(monitor, dict) else 0,
    }
    if state.get("counts") != expected_counts:
        errors.append("residual migration count reconciliation mismatch")
    return sorted(set(errors))
