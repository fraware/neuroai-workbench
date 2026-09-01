"""Reconciled noncanonical core for the Observatory-v2 predecessor migration.

This module composes only migration slices that can be represented without semantic
invention today: identity-safe v1.4 organizations as Entities, v1.4/v1.6 sources as
Sources, and exact v1.6 source checks as transport-unresolved predecessor observation
evidence. Everything else remains outside this core until its own governed mapping is
implemented.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import __version__
from .observatory_entity_migration import (
    ENTITY_MIGRATION_BOUNDARY,
    materialize_predecessor_organizations,
    verify_organization_partition,
    verify_organization_migration_record,
)
from .observatory_graph import validate_graph_object
from .observatory_migration import (
    MIGRATION_BOUNDARY,
    materialize_predecessor_sources,
    verify_predecessor_trace,
)
from .observatory_predecessor_evidence import (
    PREDECESSOR_OBSERVATION_BOUNDARY,
    preserve_v16_source_checks,
    verify_preserved_source_check,
)
from .util import atomic_write_bytes, atomic_write_json, canonical_json_bytes, sha256_bytes

CORE_MIGRATION_BOUNDARY = (
    "Noncanonical predecessor migration core. Mechanical PASS covers only native Entity/Source schema integrity, "
    "complete v1.4 organization partitioning, complete v1.4/v1.6 Source materialization, and exact preservation "
    "of transport-unresolved v1.6 source-check evidence. It does not claim complete Observatory-v2 migration, "
    "substantive truth, assessment mutation, institutional authority, or publication authorization."
)


class ObservatoryMigrationCoreError(ValueError):
    """Raised when a composed migration core violates completeness or authority boundaries."""


def _require_hex(value: Any, *, length: int, field: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(char not in "0123456789abcdef" for char in value):
        raise ObservatoryMigrationCoreError(
            f"{field} must be a lowercase {length}-character hexadecimal identity"
        )
    return value


def _object_id(record: dict[str, Any]) -> str:
    object_class = record.get("object_class")
    field = {"Entity": "entity_id", "Source": "source_id"}.get(str(object_class))
    if field is None:
        raise ObservatoryMigrationCoreError(f"Unexpected core object class {object_class!r}")
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise ObservatoryMigrationCoreError(f"Core object {object_class} missing {field}")
    return value


def build_predecessor_migration_core(
    *,
    v14_release: dict[str, Any],
    v16_refresh: dict[str, Any],
) -> dict[str, Any]:
    """Build the current loss-aware core and verify all cross-slice bindings."""
    entity_result = materialize_predecessor_organizations(v14_release)
    source_result = materialize_predecessor_sources(v14_release=v14_release, v16_refresh=v16_refresh)
    source_ids = {str(source["source_id"]) for source in source_result["sources"]}
    observation_result = preserve_v16_source_checks(v16_refresh, known_source_ids=source_ids)

    native_objects = [*entity_result["entities"], *source_result["sources"]]
    seen: set[tuple[str, str]] = set()
    schema_errors: list[str] = []
    for record in native_objects:
        object_class = str(record.get("object_class"))
        object_id = _object_id(record)
        identity = (object_class, object_id)
        if identity in seen:
            schema_errors.append(f"duplicate core object identity {object_class}:{object_id}")
        seen.add(identity)
        errors = validate_graph_object(
            {key: value for key, value in record.items() if key != "canonical_sha256"},
            object_class,
        )
        schema_errors.extend(f"{object_class}:{object_id}: {error}" for error in errors)

    result = {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "native_v2_materialization_complete": False,
        "mechanical_scope": "ENTITY_SOURCE_CORE_PLUS_PREDECESSOR_OBSERVATION_EVIDENCE",
        "native_objects": native_objects,
        "entity_migration": entity_result,
        "source_migration": source_result,
        "predecessor_observation_evidence": observation_result,
        "schema_errors": sorted(set(schema_errors)),
        "counts": {
            "input_v14_organization_records": entity_result["input_record_count"],
            "native_entities": entity_result["object_count"],
            "preserved_organization_records": entity_result["preserved_record_count"],
            "native_sources": source_result["object_count"],
            "predecessor_observation_evidence_records": observation_result[
                "predecessor_observation_evidence_count"
            ],
            "native_observations": 0,
            "native_core_objects": len(native_objects),
        },
        "remaining_unmaterialized_families": [
            "V14.organization_resolution",
            "V14.regional_expansion",
            "V14.capital_and_ownership_events",
            "V14.representative_model_records",
            "V14.model_and_dataset_registry",
            "V14.trial_site_relationships",
            "V14.participant_authority_relationships",
            "V14.supplier_dependency_relationships",
            "V14.data_quality",
            "V16.change_candidates",
            "V16.adjudicated_delta",
            "V16.reopening_decisions",
            "V16.no_change_confirmations",
            "V16.withheld_claims",
            "DELTA16.*",
            "V17.*",
            "PRIMA17.*",
        ],
        "boundaries": {
            "core": CORE_MIGRATION_BOUNDARY,
            "entity": ENTITY_MIGRATION_BOUNDARY,
            "source": MIGRATION_BOUNDARY,
            "predecessor_observation": PREDECESSOR_OBSERVATION_BOUNDARY,
        },
    }
    verification = verify_predecessor_migration_core(result)
    result["mechanical_verification"] = "PASS" if verification["valid"] else "FAIL"
    result["verification_errors"] = verification["errors"]
    return result


def verify_predecessor_migration_core(result: dict[str, Any]) -> dict[str, Any]:
    """Verify core completeness, child trace integrity, source bindings, and authority state."""
    errors: list[str] = []
    if result.get("state") != "NONCANONICAL_CANDIDATE" or result.get("release_authorized") is not False:
        errors.append("migration core must remain noncanonical and unauthorized")
    if result.get("native_v2_materialization_complete") is not False:
        errors.append("migration core must not claim complete native v2 materialization")

    entity_result = result.get("entity_migration")
    source_result = result.get("source_migration")
    observation_result = result.get("predecessor_observation_evidence")
    if not isinstance(entity_result, dict) or not isinstance(source_result, dict) or not isinstance(observation_result, dict):
        return {"valid": False, "errors": ["migration core child results are missing"]}

    entity_verification = verify_organization_partition(entity_result)
    errors.extend(f"entity: {error}" for error in entity_verification["errors"])

    sources = source_result.get("sources")
    source_traces = source_result.get("predecessor_traces")
    if not isinstance(sources, list) or not isinstance(source_traces, list) or len(sources) != len(source_traces):
        errors.append("source migration requires one trace per Source")
        sources = []
        source_traces = []
    source_ids: set[str] = set()
    for source, trace in zip(sources, source_traces, strict=False):
        if not isinstance(source, dict) or not isinstance(trace, dict):
            errors.append("source migration entries must be objects")
            continue
        source_id = str(source.get("source_id") or "")
        if not source_id or source_id in source_ids:
            errors.append(f"duplicate or empty Source id {source_id!r}")
        source_ids.add(source_id)
        errors.extend(f"source:{source_id}: {error}" for error in verify_predecessor_trace(trace, expected_native_object_id=source_id))
        schema = validate_graph_object(
            {key: value for key, value in source.items() if key != "canonical_sha256"},
            "Source",
        )
        errors.extend(f"source:{source_id}: {error}" for error in schema)

    if source_result.get("release_authorized") is not False or source_result.get("state") != "NONCANONICAL_CANDIDATE":
        errors.append("source migration child must remain noncanonical and unauthorized")

    evidence_records = observation_result.get("records")
    if not isinstance(evidence_records, list):
        errors.append("predecessor observation evidence records are missing")
        evidence_records = []
    for evidence in evidence_records:
        if not isinstance(evidence, dict):
            errors.append("predecessor observation evidence entry must be an object")
            continue
        evidence_errors = verify_preserved_source_check(evidence)
        errors.extend(f"observation-evidence: {error}" for error in evidence_errors)
        source_id = str(evidence.get("source_id") or "")
        if source_id not in source_ids:
            errors.append(f"predecessor observation evidence references missing Source {source_id}")
    if observation_result.get("native_observation_count") != 0:
        errors.append("transport-unresolved predecessor evidence cannot claim native Observations")
    if observation_result.get("release_authorized") is not False:
        errors.append("predecessor observation evidence child must remain unauthorized")

    native_objects = result.get("native_objects")
    if not isinstance(native_objects, list):
        errors.append("native_objects list is missing")
        native_objects = []
    expected_native_count = len(entity_result.get("entities", [])) + len(sources)
    if len(native_objects) != expected_native_count:
        errors.append("native_objects count does not equal Entity plus Source materialization counts")

    declared_schema_errors = result.get("schema_errors")
    if declared_schema_errors:
        errors.extend(f"core-schema: {error}" for error in declared_schema_errors)

    counts = result.get("counts")
    if not isinstance(counts, dict):
        errors.append("core counts are missing")
    else:
        expected_counts = {
            "input_v14_organization_records": entity_result.get("input_record_count"),
            "native_entities": len(entity_result.get("entities", [])),
            "preserved_organization_records": len(entity_result.get("preserved_predecessor_records", [])),
            "native_sources": len(sources),
            "predecessor_observation_evidence_records": len(evidence_records),
            "native_observations": 0,
            "native_core_objects": len(native_objects),
        }
        if counts != expected_counts:
            errors.append("core count reconciliation mismatch")

    return {"valid": not errors, "errors": sorted(set(errors))}


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for record in records]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def write_predecessor_migration_core_package(
    result: dict[str, Any],
    output_dir: Path,
    *,
    v14_input_sha256: str,
    v16_input_sha256: str,
    producer_commit: str,
    runtime_execution_pin: str,
    s2_predecessor_commit: str,
    observatory_graph_schema_version: str = "1",
) -> dict[str, Any]:
    """Write one deterministic package binding all currently representable migration-core state."""
    verification = verify_predecessor_migration_core(result)
    if not verification["valid"]:
        raise ObservatoryMigrationCoreError(f"Cannot package invalid migration core: {verification['errors']}")
    if result.get("mechanical_verification") != "PASS":
        raise ObservatoryMigrationCoreError("migration core must have mechanical PASS before packaging")

    input_v14 = _require_hex(v14_input_sha256, length=64, field="v14_input_sha256")
    input_v16 = _require_hex(v16_input_sha256, length=64, field="v16_input_sha256")
    producer = _require_hex(producer_commit, length=40, field="producer_commit")
    runtime_pin = _require_hex(runtime_execution_pin, length=40, field="runtime_execution_pin")
    s2_commit = _require_hex(s2_predecessor_commit, length=40, field="s2_predecessor_commit")
    if not isinstance(observatory_graph_schema_version, str) or not observatory_graph_schema_version.strip():
        raise ObservatoryMigrationCoreError("observatory_graph_schema_version must be non-empty")

    entity_result = result["entity_migration"]
    source_result = result["source_migration"]
    observation_result = result["predecessor_observation_evidence"]
    files = {
        "entities.jsonl": _jsonl_bytes(entity_result["entities"]),
        "entity-predecessor-traces.jsonl": _jsonl_bytes(entity_result["predecessor_traces"]),
        "preserved-organizations.jsonl": _jsonl_bytes(entity_result["preserved_predecessor_records"]),
        "sources.jsonl": _jsonl_bytes(source_result["sources"]),
        "source-predecessor-traces.jsonl": _jsonl_bytes(source_result["predecessor_traces"]),
        "predecessor-observation-evidence.jsonl": _jsonl_bytes(observation_result["records"]),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    file_digests: dict[str, str] = {}
    for path, payload in sorted(files.items()):
        atomic_write_bytes(output_dir / path, payload)
        file_digests[path] = sha256_bytes(payload)

    descriptor = {
        "schema_version": "1",
        "package_type": "OBSERVATORY_V2_PREDECESSOR_MIGRATION_CORE",
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "native_v2_materialization_complete": False,
        "mechanical_verification": "PASS",
        "mechanical_scope": result["mechanical_scope"],
        "counts": result["counts"],
        "organization_classification_counts": entity_result["classification_counts"],
        "remaining_unmaterialized_families": result["remaining_unmaterialized_families"],
        "workbench_compatibility_version": __version__,
        "producer_workbench_commit": producer,
        "runtime_execution_pin": runtime_pin,
        "observatory_graph_schema_version": observatory_graph_schema_version,
        "s2_predecessor_commit": s2_commit,
        "inputs": {"V14": input_v14, "V16": input_v16},
        "boundary": CORE_MIGRATION_BOUNDARY,
    }
    manifest = {
        "files": [{"path": path, "sha256": digest} for path, digest in sorted(file_digests.items())],
        "descriptor_sha256": sha256_bytes(canonical_json_bytes(descriptor)),
        "release_authorized": False,
        "native_v2_materialization_complete": False,
        "boundary": CORE_MIGRATION_BOUNDARY,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    atomic_write_json(output_dir / "descriptor.json", descriptor)
    atomic_write_json(output_dir / "manifest.json", manifest)
    return {"descriptor": descriptor, "manifest": manifest}
