"""DELTA16 extension for the composed noncanonical Observatory-v2 migration candidate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import __version__
from .observatory_delta_capital_migration import (
    DELTA_CAPITAL_BOUNDARY,
    materialize_delta16_capital_events,
    verify_delta_capital_event,
)
from .observatory_migration_candidate import (
    MIGRATION_CANDIDATE_BOUNDARY,
    build_predecessor_migration_candidate,
    verify_predecessor_migration_candidate,
)
from .util import atomic_write_bytes, atomic_write_json, canonical_json_bytes, sha256_bytes

DELTA_CANDIDATE_BOUNDARY = (
    "Noncanonical predecessor migration candidate extended with the complete adjudicated v1.6 capital-event "
    "delta. Mechanical PASS covers only the explicitly materialized/preserved families in the descriptor. "
    "Remaining families are unresolved; no complete migration or publication authority is established."
)


class DeltaMigrationCandidateError(ValueError):
    """Raised when the DELTA16 candidate extension does not reconcile exactly."""


def _require_hex(value: Any, *, length: int, field: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(char not in "0123456789abcdef" for char in value):
        raise DeltaMigrationCandidateError(f"{field} must be a lowercase {length}-character hexadecimal identity")
    return value


def build_predecessor_migration_candidate_with_delta(
    *,
    v14_release: dict[str, Any],
    v16_refresh: dict[str, Any],
    delta16: dict[str, Any],
) -> dict[str, Any]:
    """Extend the current candidate with the complete adjudicated DELTA16 capital-event family."""
    base = build_predecessor_migration_candidate(v14_release=v14_release, v16_refresh=v16_refresh)
    if base.get("mechanical_verification") != "PASS":
        raise DeltaMigrationCandidateError("base migration candidate must mechanically pass")
    core = base["core"]
    entities = core["entity_migration"]["entities"]
    sources = core["source_migration"]["sources"]
    source_ids = {str(item["source_id"]) for item in sources}
    delta_result = materialize_delta16_capital_events(
        delta16,
        entities=entities,
        known_source_ids=source_ids,
    )
    native_objects = [*base["native_objects"], *delta_result["events"]]
    remaining = [
        item
        for item in base["remaining_unmaterialized_families"]
        if item != "DELTA16.capital_and_ownership_events"
    ]
    result = {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "native_v2_materialization_complete": False,
        "mechanical_scope": "BASE_MIGRATION_CANDIDATE_PLUS_DELTA16_CAPITAL_EVENTS",
        "base_candidate": base,
        "delta16_capital_event_migration": delta_result,
        "native_objects": native_objects,
        "counts": {
            **base["counts"],
            "native_delta16_capital_events": delta_result["object_count"],
            "native_candidate_objects_with_delta": len(native_objects),
        },
        "remaining_unmaterialized_families": remaining,
        "boundaries": {
            "delta_candidate": DELTA_CANDIDATE_BOUNDARY,
            "base_candidate": MIGRATION_CANDIDATE_BOUNDARY,
            "delta_capital": DELTA_CAPITAL_BOUNDARY,
        },
    }
    verification = verify_predecessor_migration_candidate_with_delta(result)
    result["mechanical_verification"] = "PASS" if verification["valid"] else "FAIL"
    result["verification_errors"] = verification["errors"]
    return result


def verify_predecessor_migration_candidate_with_delta(result: dict[str, Any]) -> dict[str, Any]:
    """Verify base candidate, DELTA16 mapped fields, source/entity bindings and composed identity uniqueness."""
    errors: list[str] = []
    if result.get("state") != "NONCANONICAL_CANDIDATE" or result.get("release_authorized") is not False:
        errors.append("delta migration candidate must remain noncanonical and unauthorized")
    if result.get("native_v2_materialization_complete") is not False:
        errors.append("delta migration candidate must not claim complete native materialization")

    base = result.get("base_candidate")
    delta_result = result.get("delta16_capital_event_migration")
    if not isinstance(base, dict) or not isinstance(delta_result, dict):
        return {"valid": False, "errors": ["delta migration candidate children are missing"]}
    base_report = verify_predecessor_migration_candidate(base)
    errors.extend(f"base: {error}" for error in base_report["errors"])

    core = base.get("core", {})
    entities = core.get("entity_migration", {}).get("entities", [])
    sources = core.get("source_migration", {}).get("sources", [])
    entity_index = {
        str(item["entity_id"]): item
        for item in entities
        if isinstance(item, dict) and isinstance(item.get("entity_id"), str)
    }
    source_ids = {
        str(item["source_id"])
        for item in sources
        if isinstance(item, dict) and isinstance(item.get("source_id"), str)
    }
    events = delta_result.get("events")
    traces = delta_result.get("predecessor_traces")
    if not isinstance(events, list) or not isinstance(traces, list) or len(events) != len(traces):
        errors.append("DELTA16 capital migration requires one trace per Event")
        events = []
        traces = []
    if delta_result.get("input_record_count") != len(events):
        errors.append("DELTA16 capital migration must cover the complete family")
    if delta_result.get("release_authorized") is not False:
        errors.append("DELTA16 capital migration child must remain unauthorized")
    for event, trace in zip(events, traces, strict=False):
        if not isinstance(event, dict) or not isinstance(trace, dict):
            errors.append("DELTA16 Event/trace entries must be objects")
            continue
        event_id = str(event.get("event_id") or "")
        mapped = verify_delta_capital_event(
            event,
            trace,
            entity_index=entity_index,
            known_source_ids=source_ids,
        )
        errors.extend(f"delta-event:{event_id}: {error}" for error in mapped)

    native_objects = result.get("native_objects")
    if not isinstance(native_objects, list):
        errors.append("delta candidate native_objects list is missing")
        native_objects = []
    identities: set[tuple[str, str]] = set()
    id_fields = {
        "Entity": "entity_id",
        "Source": "source_id",
        "Event": "event_id",
        "Candidate": "candidate_id",
    }
    for record in native_objects:
        if not isinstance(record, dict):
            errors.append("delta candidate native object must be an object")
            continue
        object_class = str(record.get("object_class") or "")
        id_field = id_fields.get(object_class)
        object_id = str(record.get(id_field) or "") if id_field else ""
        if not id_field or not object_id:
            errors.append(f"unexpected or id-less native object class {object_class!r}")
            continue
        identity = (object_class, object_id)
        if identity in identities:
            errors.append(f"duplicate native object identity {object_class}:{object_id}")
        identities.add(identity)

    expected_count = len(base.get("native_objects", [])) + len(events)
    if len(native_objects) != expected_count:
        errors.append("delta candidate native object count does not reconcile")
    counts = result.get("counts")
    expected_counts = {
        **base.get("counts", {}),
        "native_delta16_capital_events": len(events),
        "native_candidate_objects_with_delta": len(native_objects),
    }
    if counts != expected_counts:
        errors.append("delta candidate count ledger mismatch")
    remaining = result.get("remaining_unmaterialized_families")
    if not isinstance(remaining, list):
        errors.append("delta candidate remaining-family ledger is missing")
    elif "DELTA16.capital_and_ownership_events" in remaining:
        errors.append("materialized DELTA16 capital family remains listed as unresolved")

    return {"valid": not errors, "errors": sorted(set(errors))}


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for record in records]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def write_predecessor_migration_candidate_with_delta_package(
    result: dict[str, Any],
    output_dir: Path,
    *,
    v14_input_sha256: str,
    v16_input_sha256: str,
    delta16_input_sha256: str,
    producer_commit: str,
    runtime_execution_pin: str,
    s2_predecessor_commit: str,
    observatory_graph_schema_version: str = "1",
) -> dict[str, Any]:
    """Write deterministic bytes for the composed candidate including the DELTA16 capital family."""
    report = verify_predecessor_migration_candidate_with_delta(result)
    if not report["valid"] or result.get("mechanical_verification") != "PASS":
        raise DeltaMigrationCandidateError(f"cannot package invalid delta candidate: {report['errors']}")
    input_v14 = _require_hex(v14_input_sha256, length=64, field="v14_input_sha256")
    input_v16 = _require_hex(v16_input_sha256, length=64, field="v16_input_sha256")
    input_delta = _require_hex(delta16_input_sha256, length=64, field="delta16_input_sha256")
    producer = _require_hex(producer_commit, length=40, field="producer_commit")
    runtime_pin = _require_hex(runtime_execution_pin, length=40, field="runtime_execution_pin")
    s2_commit = _require_hex(s2_predecessor_commit, length=40, field="s2_predecessor_commit")
    if not isinstance(observatory_graph_schema_version, str) or not observatory_graph_schema_version.strip():
        raise DeltaMigrationCandidateError("observatory_graph_schema_version must be non-empty")

    base = result["base_candidate"]
    core = base["core"]
    entity_result = core["entity_migration"]
    source_result = core["source_migration"]
    observation_result = core["predecessor_observation_evidence"]
    base_events = base["capital_event_migration"]
    change_candidates = base["change_candidate_migration"]
    delta_events = result["delta16_capital_event_migration"]
    files = {
        "entities.jsonl": _jsonl_bytes(entity_result["entities"]),
        "entity-predecessor-traces.jsonl": _jsonl_bytes(entity_result["predecessor_traces"]),
        "preserved-organizations.jsonl": _jsonl_bytes(entity_result["preserved_predecessor_records"]),
        "sources.jsonl": _jsonl_bytes(source_result["sources"]),
        "source-predecessor-traces.jsonl": _jsonl_bytes(source_result["predecessor_traces"]),
        "predecessor-observation-evidence.jsonl": _jsonl_bytes(observation_result["records"]),
        "events-v14-capital.jsonl": _jsonl_bytes(base_events["events"]),
        "event-v14-capital-traces.jsonl": _jsonl_bytes(base_events["predecessor_traces"]),
        "candidates-v16.jsonl": _jsonl_bytes(change_candidates["candidates"]),
        "candidate-v16-traces.jsonl": _jsonl_bytes(change_candidates["predecessor_traces"]),
        "events-delta16-capital.jsonl": _jsonl_bytes(delta_events["events"]),
        "event-delta16-capital-traces.jsonl": _jsonl_bytes(delta_events["predecessor_traces"]),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    file_digests: dict[str, str] = {}
    for path, payload in sorted(files.items()):
        atomic_write_bytes(output_dir / path, payload)
        file_digests[path] = sha256_bytes(payload)

    descriptor = {
        "schema_version": "1",
        "package_type": "OBSERVATORY_V2_PREDECESSOR_MIGRATION_CANDIDATE_WITH_DELTA16_CAPITAL",
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "native_v2_materialization_complete": False,
        "mechanical_verification": "PASS",
        "mechanical_scope": result["mechanical_scope"],
        "counts": result["counts"],
        "remaining_unmaterialized_families": result["remaining_unmaterialized_families"],
        "workbench_compatibility_version": __version__,
        "producer_workbench_commit": producer,
        "runtime_execution_pin": runtime_pin,
        "observatory_graph_schema_version": observatory_graph_schema_version,
        "s2_predecessor_commit": s2_commit,
        "inputs": {"V14": input_v14, "V16": input_v16, "DELTA16": input_delta},
        "boundary": DELTA_CANDIDATE_BOUNDARY,
    }
    manifest = {
        "files": [{"path": path, "sha256": digest} for path, digest in sorted(file_digests.items())],
        "descriptor_sha256": sha256_bytes(canonical_json_bytes(descriptor)),
        "release_authorized": False,
        "native_v2_materialization_complete": False,
        "boundary": DELTA_CANDIDATE_BOUNDARY,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    atomic_write_json(output_dir / "descriptor.json", descriptor)
    atomic_write_json(output_dir / "manifest.json", manifest)
    return {"descriptor": descriptor, "manifest": manifest}
