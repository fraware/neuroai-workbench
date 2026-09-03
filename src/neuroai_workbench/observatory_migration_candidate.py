"""Composed noncanonical Observatory-v2 predecessor migration candidate.

This layer extends the reconciled Entity/Source core with predecessor families that
have complete governed native mappings or explicit lossless predecessor-state
representations. It remains incomplete and cannot be used as publication authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import __version__
from .observatory_change_candidate_migration import (
    CHANGE_CANDIDATE_MIGRATION_BOUNDARY,
    materialize_v16_change_candidates,
    verify_change_candidate_trace,
)
from .observatory_event_migration import (
    EVENT_MIGRATION_BOUNDARY,
    materialize_v14_capital_events,
    verify_materialized_capital_event,
)
from .observatory_history_migration import (
    HISTORY_MIGRATION_BOUNDARY,
    preserve_v14_organization_resolution_history,
    preserve_v14_regional_expansion_history,
    verify_preserved_history_record,
)
from .observatory_migration_core import (
    CORE_MIGRATION_BOUNDARY,
    build_predecessor_migration_core,
    verify_predecessor_migration_core,
)
from .util import atomic_write_bytes, atomic_write_json, canonical_json_bytes, sha256_bytes

MIGRATION_CANDIDATE_BOUNDARY = (
    "Noncanonical Observatory-v2 predecessor migration candidate. Mechanical PASS covers only explicitly "
    "materialized and governed-preserved families named in this descriptor. Remaining predecessor families "
    "are unresolved. PASS does not establish complete migration, substantive truth, assessment mutation, "
    "institutional authority, or publication authorization."
)


class ObservatoryMigrationCandidateError(ValueError):
    """Raised when composed migration families do not reconcile exactly."""


def _require_hex(value: Any, *, length: int, field: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(char not in "0123456789abcdef" for char in value):
        raise ObservatoryMigrationCandidateError(f"{field} must be a lowercase {length}-character hexadecimal identity")
    return value


def _object_identity(record: dict[str, Any]) -> tuple[str, str]:
    object_class = str(record.get("object_class"))
    id_field = {
        "Entity": "entity_id",
        "Source": "source_id",
        "Event": "event_id",
        "Candidate": "candidate_id",
    }.get(object_class)
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
    """Build the current candidate across native and governed-preserved predecessor families."""
    core = build_predecessor_migration_core(v14_release=v14_release, v16_refresh=v16_refresh)
    if core.get("mechanical_verification") != "PASS":
        raise ObservatoryMigrationCandidateError("migration core must mechanically pass before extension")

    entities = core["entity_migration"]["entities"]
    sources = core["source_migration"]["sources"]
    source_ids = {str(source["source_id"]) for source in sources}
    entity_ids = {str(entity["entity_id"]) for entity in entities}
    organization_rows = v14_release.get("organizations")
    if not isinstance(organization_rows, list) or any(not isinstance(item, dict) for item in organization_rows):
        raise ObservatoryMigrationCandidateError("v1.4 organizations must be an array of objects")
    organization_records = {
        str(item["organization_id"]): item for item in organization_rows if isinstance(item.get("organization_id"), str)
    }
    if len(organization_records) != len(organization_rows):
        raise ObservatoryMigrationCandidateError("v1.4 organization ids must be complete and unique")

    event_result = materialize_v14_capital_events(
        v14_release,
        entities=entities,
        known_source_ids=source_ids,
    )
    change_candidate_result = materialize_v16_change_candidates(
        v16_refresh,
        known_source_ids=source_ids,
    )
    identity_history_result = preserve_v14_organization_resolution_history(
        v14_release,
        organization_records=organization_records,
        known_source_ids=source_ids,
    )
    regional_history_result = preserve_v14_regional_expansion_history(
        v14_release,
        organization_records=organization_records,
        materialized_entity_ids=entity_ids,
        known_source_ids=source_ids,
    )

    native_objects = [
        *core["native_objects"],
        *event_result["events"],
        *change_candidate_result["candidates"],
    ]
    retired_families = {
        "V14.organization_resolution",
        "V14.regional_expansion",
        "V14.capital_and_ownership_events",
        "V16.change_candidates",
    }
    remaining = [item for item in core["remaining_unmaterialized_families"] if item not in retired_families]
    result = {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "native_v2_materialization_complete": False,
        "mechanical_scope": ("MIGRATION_CORE_PLUS_V14_HISTORY_PLUS_V14_CAPITAL_EVENTS_PLUS_V16_CHANGE_CANDIDATES"),
        "core": core,
        "identity_resolution_history": identity_history_result,
        "regional_expansion_history": regional_history_result,
        "capital_event_migration": event_result,
        "change_candidate_migration": change_candidate_result,
        "native_objects": native_objects,
        "counts": {
            **core["counts"],
            "preserved_identity_resolution_history": identity_history_result["preserved_record_count"],
            "preserved_regional_expansion_history": regional_history_result["preserved_record_count"],
            "governed_predecessor_history_records": (
                identity_history_result["preserved_record_count"] + regional_history_result["preserved_record_count"]
            ),
            "native_capital_events": event_result["object_count"],
            "native_change_candidates": change_candidate_result["object_count"],
            "native_candidate_objects": len(native_objects),
        },
        "remaining_unmaterialized_families": remaining,
        "boundaries": {
            "candidate": MIGRATION_CANDIDATE_BOUNDARY,
            "core": CORE_MIGRATION_BOUNDARY,
            "history": HISTORY_MIGRATION_BOUNDARY,
            "event": EVENT_MIGRATION_BOUNDARY,
            "change_candidate": CHANGE_CANDIDATE_MIGRATION_BOUNDARY,
        },
    }
    verification = verify_predecessor_migration_candidate(result)
    result["mechanical_verification"] = "PASS" if verification["valid"] else "FAIL"
    result["verification_errors"] = verification["errors"]
    return result


def verify_predecessor_migration_candidate(result: dict[str, Any]) -> dict[str, Any]:
    """Verify candidate-wide identity uniqueness, trace integrity, and cross-family bindings."""
    errors: list[str] = []
    if result.get("state") != "NONCANONICAL_CANDIDATE" or result.get("release_authorized") is not False:
        errors.append("migration candidate must remain noncanonical and unauthorized")
    if result.get("native_v2_materialization_complete") is not False:
        errors.append("migration candidate must not claim complete native v2 materialization")

    core = result.get("core")
    identity_history = result.get("identity_resolution_history")
    regional_history = result.get("regional_expansion_history")
    event_result = result.get("capital_event_migration")
    change_candidate_result = result.get("change_candidate_migration")
    if not all(
        isinstance(item, dict)
        for item in (core, identity_history, regional_history, event_result, change_candidate_result)
    ):
        return {"valid": False, "errors": ["migration candidate child results are missing"]}
    assert isinstance(core, dict)
    assert isinstance(identity_history, dict)
    assert isinstance(regional_history, dict)
    assert isinstance(event_result, dict)
    assert isinstance(change_candidate_result, dict)

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

    predecessor_organizations: dict[str, dict[str, Any]] = {}
    entity_traces = core.get("entity_migration", {}).get("predecessor_traces", [])
    preserved_organizations = core.get("entity_migration", {}).get("preserved_predecessor_records", [])
    for trace in [*entity_traces, *preserved_organizations]:
        if not isinstance(trace, dict):
            continue
        predecessor = trace.get("predecessor_record")
        if isinstance(predecessor, dict) and isinstance(predecessor.get("organization_id"), str):
            predecessor_organizations[str(predecessor["organization_id"])] = predecessor

    for history_name, history_result in (
        ("organization_resolution", identity_history),
        ("regional_expansion", regional_history),
    ):
        records = history_result.get("records")
        if not isinstance(records, list):
            errors.append(f"{history_name} history records are missing")
            records = []
        if history_result.get("input_record_count") != len(records):
            errors.append(f"{history_name} history does not cover complete predecessor family")
        if history_result.get("preserved_record_count") != len(records):
            errors.append(f"{history_name} preserved count mismatch")
        if history_result.get("native_object_count") != 0:
            errors.append(f"{history_name} must not claim native graph objects")
        if history_result.get("release_authorized") is not False:
            errors.append(f"{history_name} history must remain unauthorized")
        for record in records:
            if not isinstance(record, dict):
                errors.append(f"{history_name} history entry must be an object")
                continue
            errors.extend(
                f"{history_name}:{record.get('record_id')}: {error}"
                for error in verify_preserved_history_record(record)
            )
            predecessor = record.get("predecessor_record")
            if not isinstance(predecessor, dict):
                continue
            org_id = str(record.get("organization_id") or "")
            organization = predecessor_organizations.get(org_id)
            if organization is None:
                errors.append(f"{history_name}:{record.get('record_id')}: predecessor organization {org_id!r} missing")
                continue
            missing_sources = sorted(set(record.get("source_ids") or []) - source_ids)
            if missing_sources:
                errors.append(f"{history_name}:{record.get('record_id')}: references missing Sources {missing_sources}")
            if history_name == "organization_resolution":
                if predecessor.get("name_before") != organization.get("canonical_name"):
                    errors.append(f"organization_resolution:{record.get('record_id')}: name_before binding mismatch")
                if predecessor.get("verification_after") != organization.get("verification_state"):
                    errors.append(
                        f"organization_resolution:{record.get('record_id')}: verification_after binding mismatch"
                    )
            else:
                entity = entity_index.get(org_id)
                if entity is None:
                    errors.append(
                        f"regional_expansion:{record.get('record_id')}: organization is not a materialized Entity"
                    )
                elif predecessor.get("canonical_name") != entity.get("canonical_label"):
                    errors.append(f"regional_expansion:{record.get('record_id')}: canonical-name binding mismatch")

    events = event_result.get("events")
    event_traces = event_result.get("predecessor_traces")
    if not isinstance(events, list) or not isinstance(event_traces, list) or len(events) != len(event_traces):
        errors.append("capital-event migration requires one trace per Event")
        events = []
        event_traces = []
    if event_result.get("input_record_count") != len(events):
        errors.append("capital-event migration must cover the complete predecessor family")
    if event_result.get("release_authorized") is not False:
        errors.append("capital-event migration child must remain unauthorized")
    for event, trace in zip(events, event_traces, strict=False):
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

    candidates = change_candidate_result.get("candidates")
    candidate_traces = change_candidate_result.get("predecessor_traces")
    if (
        not isinstance(candidates, list)
        or not isinstance(candidate_traces, list)
        or len(candidates) != len(candidate_traces)
    ):
        errors.append("change-candidate migration requires one trace per Candidate")
        candidates = []
        candidate_traces = []
    if change_candidate_result.get("input_record_count") != len(candidates):
        errors.append("change-candidate migration must cover the complete predecessor family")
    if change_candidate_result.get("release_authorized") is not False:
        errors.append("change-candidate migration child must remain unauthorized")
    for candidate, trace in zip(candidates, candidate_traces, strict=False):
        if not isinstance(candidate, dict) or not isinstance(trace, dict):
            errors.append("change Candidate/trace entries must be objects")
            continue
        candidate_id = str(candidate.get("candidate_id") or "")
        mapped_errors = verify_change_candidate_trace(
            candidate,
            trace,
            known_source_ids=source_ids,
        )
        errors.extend(f"candidate:{candidate_id}: {error}" for error in mapped_errors)

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

    expected_native_count = len(core.get("native_objects", [])) + len(events) + len(candidates)
    if len(native_objects) != expected_native_count:
        errors.append("candidate native object count does not equal composed family counts")

    counts = result.get("counts")
    if not isinstance(counts, dict):
        errors.append("candidate counts are missing")
    else:
        expected_counts = {
            **core.get("counts", {}),
            "preserved_identity_resolution_history": len(identity_history.get("records", [])),
            "preserved_regional_expansion_history": len(regional_history.get("records", [])),
            "governed_predecessor_history_records": (
                len(identity_history.get("records", [])) + len(regional_history.get("records", []))
            ),
            "native_capital_events": len(events),
            "native_change_candidates": len(candidates),
            "native_candidate_objects": len(native_objects),
        }
        if counts != expected_counts:
            errors.append("candidate count reconciliation mismatch")

    remaining = result.get("remaining_unmaterialized_families")
    retired = {
        "V14.organization_resolution",
        "V14.regional_expansion",
        "V14.capital_and_ownership_events",
        "V16.change_candidates",
    }
    if not isinstance(remaining, list):
        errors.append("remaining-family ledger is missing")
    else:
        for family in sorted(retired & set(remaining)):
            errors.append(f"remaining-family ledger did not retire governed family {family}")

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
        raise ObservatoryMigrationCandidateError(
            f"Cannot package invalid migration candidate: {verification['errors']}"
        )
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
    change_candidate_result = result["change_candidate_migration"]
    identity_history = result["identity_resolution_history"]
    regional_history = result["regional_expansion_history"]
    files = {
        "entities.jsonl": _jsonl_bytes(entity_result["entities"]),
        "entity-predecessor-traces.jsonl": _jsonl_bytes(entity_result["predecessor_traces"]),
        "preserved-organizations.jsonl": _jsonl_bytes(entity_result["preserved_predecessor_records"]),
        "sources.jsonl": _jsonl_bytes(source_result["sources"]),
        "source-predecessor-traces.jsonl": _jsonl_bytes(source_result["predecessor_traces"]),
        "predecessor-observation-evidence.jsonl": _jsonl_bytes(observation_result["records"]),
        "identity-resolution-history.jsonl": _jsonl_bytes(identity_history["records"]),
        "regional-expansion-history.jsonl": _jsonl_bytes(regional_history["records"]),
        "events.jsonl": _jsonl_bytes(event_result["events"]),
        "event-predecessor-traces.jsonl": _jsonl_bytes(event_result["predecessor_traces"]),
        "candidates.jsonl": _jsonl_bytes(change_candidate_result["candidates"]),
        "candidate-predecessor-traces.jsonl": _jsonl_bytes(change_candidate_result["predecessor_traces"]),
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
