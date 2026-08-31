"""Composed noncanonical Observatory-v2 predecessor migration candidate.

This layer extends the reconciled Entity/Source core with predecessor families that
have complete governed native mappings. It remains explicitly incomplete and cannot
be used as publication authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import __version__
from .observatory_event_migration import (
    EVENT_MIGRATION_BOUNDARY,
    materialize_v14_capital_events,
    verify_materialized_capital_event,
)
from .observatory_migration_core import (
    CORE_MIGRATION_BOUNDARY,
    build_predecessor_migration_core,
    verify_predecessor_migration_core,
)
from .util import atomic_write_bytes, atomic_write_json, canonical_json_bytes, sha256_bytes

MIGRATION_CANDIDATE_BOUNDARY = (
    "Noncanonical Observatory-v2 predecessor migration candidate. Mechanical PASS covers only explicitly "
    "materialized and preserved families named in this descriptor. Remaining predecessor families are still "
    "unmaterialized. PASS does not establish complete migration, substantive truth, assessment mutation, "
    "institutional authority, or publication authorization."
)


class ObservatoryMigrationCandidateError(ValueError):
    """Raised when composed migration families do not reconcile exactly."""


def _require_hex(value: Any, *, length: int, field: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(char not in "0123456789abcdef" for char in value):
        raise ObservatoryMigrationCandidateError(
            f"{field} must be a lowercase {length}-character hexadecimal identity"
        )
    return value


def _object_identity(record: dict[str, Any]) -> tuple[str, str]:
    object_class = str(record.get("object_class"))
    id_field = {"Entity": "entity_id", "Source": "source_id", "Event": "event_id"}.get(object_class)
    if id_field is None:
        raise ObservatoryMigrationCandidateError(f"Unexpected candidate object class {object_class!r}")
    value = record.get(id_field)
    if not isinstance(value, str) or not value:
        raise ObservatoryMigrationCandidateError(f"Candidate object {object_class} missing {id_field}")
    return object_class, value


def build_predecessor_migration_candidate(
    *,
    v14_release: dict[str, Any],
    v16_refresh: dict[str, Any],
) -> dict[str, Any]:
    """Build the current composed candidate: migration core plus complete v1.4 capital events."""
    core = build_predecessor_migration_core(v14_release=v14_release, v16_refresh=v16_refresh)
    if core.get("mechanical_verification") != "PASS":
        raise ObservatoryMigrationCandidateError("migration core must mechanically pass before extension")

    entities = core["entity_migration"]["entities"]
    sources = core["source_migration"]["sources"]
    source_ids = {str(source["source_id"]) for source in sources}
    event_result = materialize_v14_capital_events(
        v14_release,
        entities=entities,
        known_source_ids=source_ids,
    )

    native_objects = [*core["native_objects"], *event_result["events"]]
    remaining = [
        item
        for item in core["remaining_unmaterialized_families"]
        if item != "V14.capital_and_ownership_events"
    ]
    result = {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "native_v2_materialization_complete": False,
        "mechanical_scope": "MIGRATION_CORE_PLUS_V14_CAPITAL_EVENTS",
        "core": core,
        "capital_event_migration": event_result,
        "native_objects": native_objects,
        "counts": {
            **core["counts"],
            "native_capital_events": event_result["object_count"],
            "native_candidate_objects": len(native_objects),
        },
        "remaining_unmaterialized_families": remaining,
        "boundaries": {
            "candidate": MIGRATION_CANDIDATE_BOUNDARY,
            "core": CORE_MIGRATION_BOUNDARY,
            "event": EVENT_MIGRATION_BOUNDARY,
        },
    }
    verification = verify_predecessor_migration_candidate(result)
    result["mechanical_verification"] = "PASS" if verification["valid"] else "FAIL"
    result["verification_errors"] = verification["errors"]
    return result


def verify_predecessor_migration_candidate(result: dict[str, Any]) -> dict[str, Any]:
    """Verify candidate-wide class/id uniqueness and exact cross-object event bindings."""
    errors: list[str] = []
    if result.get("state") != "NONCANONICAL_CANDIDATE" or result.get("release_authorized") is not False:
        errors.append("migration candidate must remain noncanonical and unauthorized")
    if result.get("native_v2_materialization_complete") is not False:
        errors.append("migration candidate must not claim complete native v2 materialization")

    core = result.get("core")
    event_result = result.get("capital_event_migration")
    if not isinstance(core, dict) or not isinstance(event_result, dict):
        return {"valid": False, "errors": ["migration candidate child results are missing"]}
    core_report = verify_predecessor_migration_core(core)
    errors.extend(f"core: {error}" for error in core_report["errors"])

    entities = core.get("entity_migration", {}).get("entities", [])
    sources = core.get("source_migration", {}).get("sources", [])
    if not isinstance(entities, list) or not isinstance(sources, list):
        errors.append("candidate Entity/Source lists are missing")
        entities = []
        sources = []
    entity_index: dict[str, dict[str, Any]] = {}
    for entity in entities:
        if not isinstance(entity, dict):
            errors.append("candidate Entity entry must be an object")
            continue
        entity_id = str(entity.get("entity_id") or "")
        if not entity_id or entity_id in entity_index:
            errors.append(f"duplicate or empty Entity id {entity_id!r}")
        entity_index[entity_id] = entity
    source_ids = {
        str(source.get("source_id"))
        for source in sources
        if isinstance(source, dict) and isinstance(source.get("source_id"), str)
    }

    events = event_result.get("events")
    traces = event_result.get("predecessor_traces")
    if not isinstance(events, list) or not isinstance(traces, list) or len(events) != len(traces):
        errors.append("capital-event migration requires one trace per Event")
        events = []
        traces = []
    if event_result.get("input_record_count") != len(events):
        errors.append("capital-event migration must cover the complete predecessor family")
    if event_result.get("release_authorized") is not False:
        errors.append("capital-event migration child must remain unauthorized")

    for event, trace in zip(events, traces, strict=False):
        if not isinstance(event, dict) or not isinstance(trace, dict):
            errors.append("capital Event/trace entries must be objects")
            continue
        event_id = str(event.get("event_id") or "")
        mapped_errors = verify_materialized_capital_event(
            event,
            trace,
            entity_index=entity_index,
            known_source_ids=source_ids,
        )
        errors.extend(f"event:{event_id}: {error}" for error in mapped_errors)

    native_objects = result.get("native_objects")
    if not isinstance(native_objects, list):
        errors.append("candidate native_objects list is missing")
        native_objects = []
    seen: set[tuple[str, str]] = set()
    for record in native_objects:
        if not isinstance(record, dict):
            errors.append("candidate native object must be an object")
            continue
        try:
            identity = _object_identity(record)
        except ObservatoryMigrationCandidateError as exc:
            errors.append(str(exc))
            continue
        if identity in seen:
            errors.append(f"duplicate candidate object identity {identity[0]}:{identity[1]}")
        seen.add(identity)

    expected_native_count = len(core.get("native_objects", [])) + len(events)
    if len(native_objects) != expected_native_count:
        errors.append("candidate native object count does not equal core plus event counts")

    counts = result.get("counts")
    if not isinstance(counts, dict):
        errors.append("candidate counts are missing")
    else:
        expected_counts = {
            **core.get("counts", {}),
            "native_capital_events": len(events),
            "native_candidate_objects": len(native_objects),
        }
        if counts != expected_counts:
            errors.append("candidate count reconciliation mismatch")

    remaining = result.get("remaining_unmaterialized_families")
    if not isinstance(remaining, list) or "V14.capital_and_ownership_events" in remaining:
        errors.append("remaining-family ledger did not retire the materialized capital-event family")

    return {"valid": not errors, "errors": sorted(set(errors))}


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for record in records]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def write_predecessor_migration_candidate_package(
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
    """Write the deterministic composed candidate and all exact predecessor trace surfaces."""
    verification = verify_predecessor_migration_candidate(result)
    if not verification["valid"]:
        raise ObservatoryMigrationCandidateError(f"Cannot package invalid migration candidate: {verification['errors']}")
    if result.get("mechanical_verification") != "PASS":
        raise ObservatoryMigrationCandidateError("migration candidate must have mechanical PASS before packaging")

    input_v14 = _require_hex(v14_input_sha256, length=64, field="v14_input_sha256")
    input_v16 = _require_hex(v16_input_sha256, length=64, field="v16_input_sha256")
    producer = _require_hex(producer_commit, length=40, field="producer_commit")
    runtime_pin = _require_hex(runtime_execution_pin, length=40, field="runtime_execution_pin")
    s2_commit = _require_hex(s2_predecessor_commit, length=40, field="s2_predecessor_commit")
    if not isinstance(observatory_graph_schema_version, str) or not observatory_graph_schema_version.strip():
        raise ObservatoryMigrationCandidateError("observatory_graph_schema_version must be non-empty")

    core = result["core"]
    entity_result = core["entity_migration"]
    source_result = core["source_migration"]
    observation_result = core["predecessor_observation_evidence"]
    event_result = result["capital_event_migration"]
    files = {
        "entities.jsonl": _jsonl_bytes(entity_result["entities"]),
        "entity-predecessor-traces.jsonl": _jsonl_bytes(entity_result["predecessor_traces"]),
        "preserved-organizations.jsonl": _jsonl_bytes(entity_result["preserved_predecessor_records"]),
        "sources.jsonl": _jsonl_bytes(source_result["sources"]),
        "source-predecessor-traces.jsonl": _jsonl_bytes(source_result["predecessor_traces"]),
        "predecessor-observation-evidence.jsonl": _jsonl_bytes(observation_result["records"]),
        "events.jsonl": _jsonl_bytes(event_result["events"]),
        "event-predecessor-traces.jsonl": _jsonl_bytes(event_result["predecessor_traces"]),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    file_digests: dict[str, str] = {}
    for path, payload in sorted(files.items()):
        atomic_write_bytes(output_dir / path, payload)
        file_digests[path] = sha256_bytes(payload)

    descriptor = {
        "schema_version": "1",
        "package_type": "OBSERVATORY_V2_PREDECESSOR_MIGRATION_CANDIDATE",
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
        "boundary": MIGRATION_CANDIDATE_BOUNDARY,
    }
    manifest = {
        "files": [{"path": path, "sha256": digest} for path, digest in sorted(file_digests.items())],
        "descriptor_sha256": sha256_bytes(canonical_json_bytes(descriptor)),
        "release_authorized": False,
        "native_v2_materialization_complete": False,
        "boundary": MIGRATION_CANDIDATE_BOUNDARY,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    atomic_write_json(output_dir / "descriptor.json", descriptor)
    atomic_write_json(output_dir / "manifest.json", manifest)
    return {"descriptor": descriptor, "manifest": manifest}
