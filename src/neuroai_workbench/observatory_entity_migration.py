"""Identity-safe predecessor organization migration for Observatory v2.

The predecessor v1.4 organization array is heterogeneous. Only records whose exact
controlled organization id and current identity state are already governed may become
native v2 Entity objects automatically. Legacy relationship endpoints, provenance-only
nodes, and historical records whose current identity is not established remain explicit
content-addressed predecessor state.

Nothing in this module grants canonical publication authority or upgrades predecessor
evidence, verification, performance, safety, regulatory, or conformance claims.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from . import __version__
from .observatory_graph import build_entity, validate_graph_object
from .util import atomic_write_bytes, atomic_write_json, canonical_json_bytes, sha256_bytes

ENTITY_MIGRATION_BOUNDARY = (
    "Exact predecessor organization identity migration only. Native Entity materialization is restricted to "
    "already-controlled current organization ids with governed current identity state. Native entity_type is "
    "the v2 ontology class ORGANIZATION; predecessor organization_type remains trace state for later bounded "
    "assertion mapping. Legacy endpoints, provenance-only nodes, and historical/current-identity-unresolved "
    "records remain predecessor state. Entity materialization does not establish substantive truth, current "
    "capability, regulatory status, conformance, institutional endorsement, or release authority."
)

MATERIALIZE_ACTIVE_ENTITY = "MATERIALIZE_ACTIVE_ENTITY"
LEGACY_IDENTITY_UNRESOLVED = "LEGACY_IDENTITY_UNRESOLVED"
PROVENANCE_ONLY_NODE = "PROVENANCE_ONLY_NODE"
HISTORICAL_CURRENT_IDENTITY_UNRESOLVED = "HISTORICAL_CURRENT_IDENTITY_UNRESOLVED"
NATIVE_ENTITY_TYPE = "ORGANIZATION"
DEFAULT_LINEAGE = {
    "predecessor_entity_ids": [],
    "successor_entity_ids": [],
    "supersession_state": "NONE",
}

SAFE_VERIFICATION_STATES = frozenset(
    {
        "CURRENT_VERIFIED",
        "CURRENT_PARTIAL",
        "CURRENT_VERIFIED_RESCOPED",
        "CURRENT_VERIFIED_CORRECTED",
    }
)
SAFE_CURRENT_STATUSES = frozenset({"ACTIVE_OR_CURRENTLY_REPRESENTED", "CURRENT"})


class ObservatoryEntityMigrationError(ValueError):
    """Raised when an organization record cannot be classified or materialized without invention."""


def _require_hex(value: Any, *, length: int, field: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(char not in "0123456789abcdef" for char in value):
        raise ObservatoryEntityMigrationError(f"{field} must be a lowercase {length}-character hexadecimal identity")
    return value


def _record_digest(record: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(record))


def classify_predecessor_organization(record: dict[str, Any]) -> str:
    """Classify one v1.4 organization-array record under the migration identity contract.

    Classification is exact-state based. It never uses fuzzy names, inferred currentness,
    web availability, or migration-time lookups.
    """
    if not isinstance(record, dict):
        raise ObservatoryEntityMigrationError("Predecessor organization record must be an object")

    verification_state = str(record.get("verification_state") or "")
    current_status = str(record.get("current_status") or "")
    organization_type = str(record.get("organization_type") or "")

    if verification_state == "NON_ORGANIZATION_PROVENANCE_NODE" or current_status == "RECLASSIFIED":
        if verification_state != "NON_ORGANIZATION_PROVENANCE_NODE" or current_status != "RECLASSIFIED":
            raise ObservatoryEntityMigrationError(
                "Provenance-node classification requires both NON_ORGANIZATION_PROVENANCE_NODE and RECLASSIFIED"
            )
        return PROVENANCE_ONLY_NODE

    if verification_state == "LEGACY_ONLY" or organization_type == "LEGACY_STUB":
        if verification_state != "LEGACY_ONLY" or organization_type != "LEGACY_STUB":
            raise ObservatoryEntityMigrationError(
                "Legacy identity classification requires both LEGACY_ONLY and LEGACY_STUB"
            )
        return LEGACY_IDENTITY_UNRESOLVED

    if verification_state == "HISTORICAL_ARCHIVED" or current_status == "HISTORICAL_ARCHIVED":
        if verification_state != "HISTORICAL_ARCHIVED" or current_status != "HISTORICAL_ARCHIVED":
            raise ObservatoryEntityMigrationError(
                "Historical identity classification requires matching HISTORICAL_ARCHIVED states"
            )
        return HISTORICAL_CURRENT_IDENTITY_UNRESOLVED

    if verification_state in SAFE_VERIFICATION_STATES and current_status in SAFE_CURRENT_STATUSES:
        return MATERIALIZE_ACTIVE_ENTITY

    raise ObservatoryEntityMigrationError(
        "Unreviewed predecessor organization identity state: "
        f"verification_state={verification_state!r}, current_status={current_status!r}, "
        f"organization_type={organization_type!r}"
    )


def _validate_core_identity(record: dict[str, Any]) -> tuple[str, str, list[str]]:
    organization_id = record.get("organization_id")
    canonical_name = record.get("canonical_name")
    organization_type = record.get("organization_type")
    aliases = record.get("aliases")

    if not isinstance(organization_id, str) or not organization_id.strip():
        raise ObservatoryEntityMigrationError("Materializable organization requires a non-empty organization_id")
    if not isinstance(canonical_name, str) or not canonical_name.strip():
        raise ObservatoryEntityMigrationError("Materializable organization requires a non-empty canonical_name")
    if not isinstance(organization_type, str) or not organization_type.strip():
        raise ObservatoryEntityMigrationError("Materializable organization requires predecessor organization_type")
    if not isinstance(aliases, list) or any(not isinstance(alias, str) for alias in aliases):
        raise ObservatoryEntityMigrationError("Materializable organization aliases must be an array of strings")
    return organization_id, canonical_name, list(aliases)


def _native_trace(*, record: dict[str, Any], record_index: int, entity_id: str) -> dict[str, Any]:
    return {
        "role": "V14",
        "family": "organizations",
        "record_index": record_index,
        "classification": MATERIALIZE_ACTIVE_ENTITY,
        "native_object_class": "Entity",
        "native_object_id": entity_id,
        "predecessor_record_sha256": _record_digest(record),
        "predecessor_record": record,
        "migration_generated_fields": {
            "entity_type": NATIVE_ENTITY_TYPE,
            "status": "ACTIVE",
            "identifiers": [],
            "lineage": DEFAULT_LINEAGE,
        },
        "native_authority": False,
        "boundary": ENTITY_MIGRATION_BOUNDARY,
    }


def _preserved_record(*, record: dict[str, Any], record_index: int, classification: str) -> dict[str, Any]:
    return {
        "role": "V14",
        "family": "organizations",
        "record_index": record_index,
        "classification": classification,
        "native_object_class": None,
        "native_object_id": None,
        "predecessor_record_sha256": _record_digest(record),
        "predecessor_record": record,
        "native_authority": False,
        "boundary": ENTITY_MIGRATION_BOUNDARY,
    }


def verify_organization_migration_record(
    trace: dict[str, Any],
    *,
    expected_native_object_id: str | None = None,
) -> list[str]:
    """Verify exact predecessor bytes, classification, and native binding for one migration record."""
    errors: list[str] = []
    record = trace.get("predecessor_record")
    if not isinstance(record, dict):
        errors.append("predecessor_record must be an object")
        return errors

    if trace.get("predecessor_record_sha256") != _record_digest(record):
        errors.append("predecessor_record_sha256 mismatch")
    if trace.get("role") != "V14" or trace.get("family") != "organizations":
        errors.append("organization migration role/family mismatch")
    if trace.get("native_authority") is not False:
        errors.append("native_authority must remain false")
    if trace.get("boundary") != ENTITY_MIGRATION_BOUNDARY:
        errors.append("entity migration boundary mismatch")
    if not isinstance(trace.get("record_index"), int) or int(trace["record_index"]) < 0:
        errors.append("record_index must be a non-negative integer")

    try:
        expected_classification = classify_predecessor_organization(record)
    except ObservatoryEntityMigrationError as exc:
        errors.append(str(exc))
        return errors

    if trace.get("classification") != expected_classification:
        errors.append("organization classification mismatch")

    native_class = trace.get("native_object_class")
    native_id = trace.get("native_object_id")
    if expected_classification == MATERIALIZE_ACTIVE_ENTITY:
        record_id = str(record.get("organization_id") or "")
        if native_class != "Entity":
            errors.append("materializable organization must bind native Entity")
        if native_id != record_id:
            errors.append("native entity id must equal exact predecessor organization_id")
        if expected_native_object_id is not None and native_id != expected_native_object_id:
            errors.append("native_object_id binding mismatch")
        expected_generated = {
            "entity_type": NATIVE_ENTITY_TYPE,
            "status": "ACTIVE",
            "identifiers": [],
            "lineage": DEFAULT_LINEAGE,
        }
        if trace.get("migration_generated_fields") != expected_generated:
            errors.append("organization migration-generated field declaration mismatch")
    else:
        if native_class is not None or native_id is not None:
            errors.append("preserved organization state must not bind a native object")
        if "migration_generated_fields" in trace:
            errors.append("preserved organization state must not declare native generated fields")

    return sorted(set(errors))


def verify_materialized_organization(entity: dict[str, Any], trace: dict[str, Any]) -> list[str]:
    """Verify every native Entity identity field against the exact predecessor record and ontology."""
    errors = verify_organization_migration_record(
        trace,
        expected_native_object_id=str(entity.get("entity_id") or ""),
    )
    predecessor = trace.get("predecessor_record")
    if not isinstance(predecessor, dict):
        return sorted(set(errors + ["predecessor_record must be an object"]))
    if entity.get("entity_id") != predecessor.get("organization_id"):
        errors.append("Entity.entity_id binding mismatch")
    if entity.get("canonical_label") != predecessor.get("canonical_name"):
        errors.append("Entity.canonical_label binding mismatch")
    if entity.get("aliases") != predecessor.get("aliases"):
        errors.append("Entity.aliases binding mismatch")
    if entity.get("entity_type") != NATIVE_ENTITY_TYPE:
        errors.append("Entity.entity_type must be ORGANIZATION under v2 ontology")
    if entity.get("status") != "ACTIVE":
        errors.append("migration Entity.status must remain ACTIVE for materialized current identities")
    if entity.get("identifiers") != []:
        errors.append("migration Entity.identifiers must remain empty until separately governed")
    if entity.get("lineage") != DEFAULT_LINEAGE:
        errors.append("migration Entity.lineage must remain empty until separately governed")
    if entity.get("boundary") != ENTITY_MIGRATION_BOUNDARY:
        errors.append("Entity migration boundary mismatch")
    schema_errors = validate_graph_object(
        {key: value for key, value in entity.items() if key != "canonical_sha256"},
        "Entity",
    )
    errors.extend(f"schema: {error}" for error in schema_errors)
    return sorted(set(errors))


def materialize_predecessor_organization(
    record: dict[str, Any],
    *,
    record_index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Materialize one identity-safe current predecessor organization as a v2 ORGANIZATION Entity."""
    classification = classify_predecessor_organization(record)
    if classification != MATERIALIZE_ACTIVE_ENTITY:
        raise ObservatoryEntityMigrationError(
            f"Organization classification {classification} is not eligible for native Entity materialization"
        )

    organization_id, canonical_name, aliases = _validate_core_identity(record)
    entity = build_entity(
        entity_id=organization_id,
        entity_type=NATIVE_ENTITY_TYPE,
        canonical_label=canonical_name,
        aliases=aliases,
        identifiers=[],
        status="ACTIVE",
        lineage=DEFAULT_LINEAGE,
        boundary=ENTITY_MIGRATION_BOUNDARY,
    )
    trace = _native_trace(record=record, record_index=record_index, entity_id=organization_id)
    errors = verify_materialized_organization(entity, trace)
    if errors:
        raise ObservatoryEntityMigrationError(f"Generated organization Entity/trace is invalid: {errors}")
    return entity, trace


def materialize_predecessor_organizations(v14_release: dict[str, Any]) -> dict[str, Any]:
    """Partition all v1.4 organization-array records and materialize only identity-safe Entities."""
    records = v14_release.get("organizations")
    if not isinstance(records, list):
        raise ObservatoryEntityMigrationError("Expected v1.4 organizations array")

    entities: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    preserved: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    seen_ids: set[str] = set()

    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            raise ObservatoryEntityMigrationError(f"v1.4 organization record {index} must be an object")
        classification = classify_predecessor_organization(raw)
        counts[classification] += 1

        if classification == MATERIALIZE_ACTIVE_ENTITY:
            entity, trace = materialize_predecessor_organization(raw, record_index=index)
            entity_id = str(entity["entity_id"])
            if entity_id in seen_ids:
                raise ObservatoryEntityMigrationError(f"Duplicate materialized entity id {entity_id}")
            seen_ids.add(entity_id)
            entities.append(entity)
            traces.append(trace)
        else:
            item = _preserved_record(record=raw, record_index=index, classification=classification)
            errors = verify_organization_migration_record(item)
            if errors:
                raise ObservatoryEntityMigrationError(f"Generated preserved organization state is invalid: {errors}")
            preserved.append(item)

    result = {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "object_class": "Entity",
        "input_record_count": len(records),
        "object_count": len(entities),
        "predecessor_trace_count": len(traces),
        "preserved_record_count": len(preserved),
        "classification_counts": dict(sorted(counts.items())),
        "entities": entities,
        "predecessor_traces": traces,
        "preserved_predecessor_records": preserved,
        "migration_generated_metadata": {
            "native_entity_type": NATIVE_ENTITY_TYPE,
            "native_status": "ACTIVE",
            "identifiers": [],
            "lineage": DEFAULT_LINEAGE,
            "boundary": ENTITY_MIGRATION_BOUNDARY,
        },
        "boundary": ENTITY_MIGRATION_BOUNDARY,
    }
    verification = verify_organization_partition(result)
    if not verification["valid"]:
        raise ObservatoryEntityMigrationError(f"Organization migration partition is invalid: {verification['errors']}")
    return result


def verify_organization_partition(result: dict[str, Any]) -> dict[str, Any]:
    """Verify a complete partition: every predecessor record appears exactly once as native or preserved."""
    errors: list[str] = []
    entities = result.get("entities")
    traces = result.get("predecessor_traces")
    preserved = result.get("preserved_predecessor_records")
    if not isinstance(entities, list) or not isinstance(traces, list) or not isinstance(preserved, list):
        return {"valid": False, "errors": ["partition lists are missing"]}
    if len(entities) != len(traces):
        errors.append("one native trace is required per materialized Entity")

    indexes: list[int] = []
    entity_ids: set[str] = set()
    for entity, trace in zip(entities, traces, strict=False):
        if not isinstance(entity, dict) or not isinstance(trace, dict):
            errors.append("native Entity/trace entries must be objects")
            continue
        entity_id = str(entity.get("entity_id") or "")
        if not entity_id or entity_id in entity_ids:
            errors.append(f"duplicate or empty materialized entity id {entity_id!r}")
        entity_ids.add(entity_id)
        errors.extend(verify_materialized_organization(entity, trace))
        if isinstance(trace.get("record_index"), int):
            indexes.append(int(trace["record_index"]))

    for item in preserved:
        if not isinstance(item, dict):
            errors.append("preserved organization entries must be objects")
            continue
        errors.extend(verify_organization_migration_record(item))
        if isinstance(item.get("record_index"), int):
            indexes.append(int(item["record_index"]))

    input_count = result.get("input_record_count")
    if not isinstance(input_count, int) or input_count < 0:
        errors.append("input_record_count must be a non-negative integer")
    else:
        expected_indexes = list(range(input_count))
        if sorted(indexes) != expected_indexes:
            errors.append("organization partition does not cover every input record exactly once")
        if len(entities) + len(preserved) != input_count:
            errors.append("native plus preserved organization counts do not equal input count")

    observed_counts = Counter(str(trace.get("classification")) for trace in traces if isinstance(trace, dict))
    observed_counts.update(str(item.get("classification")) for item in preserved if isinstance(item, dict))
    declared_counts = result.get("classification_counts")
    if declared_counts != dict(sorted(observed_counts.items())):
        errors.append("classification_counts mismatch")
    expected_metadata = {
        "native_entity_type": NATIVE_ENTITY_TYPE,
        "native_status": "ACTIVE",
        "identifiers": [],
        "lineage": DEFAULT_LINEAGE,
        "boundary": ENTITY_MIGRATION_BOUNDARY,
    }
    if result.get("migration_generated_metadata") != expected_metadata:
        errors.append("organization migration-generated metadata mismatch")
    if result.get("release_authorized") is not False or result.get("state") != "NONCANONICAL_CANDIDATE":
        errors.append("organization migration result must remain noncanonical and unauthorized")

    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "input_record_count": input_count,
        "materialized_entity_count": len(entities),
        "preserved_record_count": len(preserved),
    }


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for record in records]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def write_predecessor_entity_package(
    result: dict[str, Any],
    output_dir: Path,
    *,
    v14_input_sha256: str,
    producer_commit: str,
    runtime_execution_pin: str,
    s2_predecessor_commit: str,
    observatory_graph_schema_version: str = "1",
) -> dict[str, Any]:
    """Write a deterministic noncanonical Entity migration package with complete partition evidence."""
    verification = verify_organization_partition(result)
    if not verification["valid"]:
        raise ObservatoryEntityMigrationError(
            f"Cannot package invalid organization partition: {verification['errors']}"
        )

    input_v14 = _require_hex(v14_input_sha256, length=64, field="v14_input_sha256")
    producer = _require_hex(producer_commit, length=40, field="producer_commit")
    runtime_pin = _require_hex(runtime_execution_pin, length=40, field="runtime_execution_pin")
    s2_commit = _require_hex(s2_predecessor_commit, length=40, field="s2_predecessor_commit")
    if not isinstance(observatory_graph_schema_version, str) or not observatory_graph_schema_version.strip():
        raise ObservatoryEntityMigrationError("observatory_graph_schema_version must be non-empty")

    entities = result["entities"]
    traces = result["predecessor_traces"]
    preserved = result["preserved_predecessor_records"]
    output_dir.mkdir(parents=True, exist_ok=True)

    entity_bytes = _jsonl_bytes(entities)
    trace_bytes = _jsonl_bytes(traces)
    preserved_bytes = _jsonl_bytes(preserved)
    atomic_write_bytes(output_dir / "entities.jsonl", entity_bytes)
    atomic_write_bytes(output_dir / "predecessor-traces.jsonl", trace_bytes)
    atomic_write_bytes(output_dir / "preserved-organizations.jsonl", preserved_bytes)

    file_digests = {
        "entities.jsonl": sha256_bytes(entity_bytes),
        "predecessor-traces.jsonl": sha256_bytes(trace_bytes),
        "preserved-organizations.jsonl": sha256_bytes(preserved_bytes),
    }
    descriptor = {
        "schema_version": "1",
        "package_type": "OBSERVATORY_V2_PREDECESSOR_ENTITY_MIGRATION",
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "input_record_count": result["input_record_count"],
        "object_count": result["object_count"],
        "preserved_record_count": result["preserved_record_count"],
        "classification_counts": result["classification_counts"],
        "workbench_compatibility_version": __version__,
        "producer_workbench_commit": producer,
        "runtime_execution_pin": runtime_pin,
        "observatory_graph_schema_version": observatory_graph_schema_version,
        "s2_predecessor_commit": s2_commit,
        "inputs": {"V14": input_v14},
        "migration_generated_metadata": result.get("migration_generated_metadata"),
        "boundary": ENTITY_MIGRATION_BOUNDARY,
    }
    manifest = {
        "files": [{"path": path, "sha256": digest} for path, digest in sorted(file_digests.items())],
        "descriptor_sha256": sha256_bytes(canonical_json_bytes(descriptor)),
        "release_authorized": False,
        "boundary": ENTITY_MIGRATION_BOUNDARY,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    atomic_write_json(output_dir / "descriptor.json", descriptor)
    atomic_write_json(output_dir / "manifest.json", manifest)
    return {"descriptor": descriptor, "manifest": manifest}
