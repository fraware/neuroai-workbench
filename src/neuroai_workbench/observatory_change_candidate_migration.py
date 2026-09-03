"""Lossless native Candidate migration for v1.6 change-candidate records.

The v1.6 change-candidate family already carries stable controlled candidate ids,
change classes, adjudication states, bounded source references, and complete predecessor
payloads. Migration stores the exact predecessor record as Candidate.payload and uses
OFFLINE_REPLAY only to describe the migration execution path; it does not re-adjudicate
the candidate or resolve its free-text subject into a graph entity.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import __version__
from .observatory_graph import build_candidate, validate_graph_object
from .util import atomic_write_bytes, atomic_write_json, canonical_json_bytes, sha256_bytes

CHANGE_CANDIDATE_MIGRATION_BOUNDARY = (
    "Exact v1.6 change-candidate migration. Candidate id, class, adjudication state, source references and the "
    "complete predecessor payload are preserved. OFFLINE_REPLAY describes migration execution only. Free-text "
    "subjects remain payload text and are not promoted to resolved graph entities. Native Candidate state does "
    "not establish substantive truth, reopen an assessment, mutate S2, or authorize publication."
)
MIGRATION_PROVENANCE_MODE = "OFFLINE_REPLAY"


class ObservatoryChangeCandidateMigrationError(ValueError):
    """Raised when a predecessor change candidate cannot be migrated exactly."""


def _require_hex(value: Any, *, length: int, field: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(char not in "0123456789abcdef" for char in value):
        raise ObservatoryChangeCandidateMigrationError(
            f"{field} must be a lowercase {length}-character hexadecimal identity"
        )
    return value


def _record_digest(record: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(record))


def verify_change_candidate_trace(
    candidate: dict[str, Any],
    trace: dict[str, Any],
    *,
    known_source_ids: set[str],
) -> list[str]:
    """Verify every native Candidate mapping against the exact predecessor record."""
    errors: list[str] = []
    predecessor = trace.get("predecessor_record")
    if not isinstance(predecessor, dict):
        return ["predecessor_record must be an object"]
    if trace.get("predecessor_record_sha256") != _record_digest(predecessor):
        errors.append("predecessor_record_sha256 mismatch")
    if trace.get("role") != "V16" or trace.get("family") != "change_candidates":
        errors.append("change-candidate migration role/family mismatch")
    if trace.get("native_object_class") != "Candidate":
        errors.append("change-candidate trace must bind native Candidate")
    if trace.get("native_authority") is not False:
        errors.append("native_authority must remain false")
    if trace.get("boundary") != CHANGE_CANDIDATE_MIGRATION_BOUNDARY:
        errors.append("change-candidate trace boundary mismatch")
    if not isinstance(trace.get("record_index"), int) or int(trace["record_index"]) < 0:
        errors.append("record_index must be a non-negative integer")

    candidate_id = predecessor.get("candidate_id")
    change_class = predecessor.get("change_class")
    adjudication = predecessor.get("adjudication")
    source_ids = predecessor.get("source_ids")
    if candidate.get("candidate_id") != candidate_id or trace.get("native_object_id") != candidate_id:
        errors.append("candidate_id binding mismatch")
    if candidate.get("candidate_class") != change_class:
        errors.append("candidate_class binding mismatch")
    if candidate.get("status") != adjudication:
        errors.append("candidate status/adjudication binding mismatch")
    if candidate.get("payload") != predecessor:
        errors.append("Candidate.payload must equal exact predecessor record")
    if candidate.get("provenance_mode") != MIGRATION_PROVENANCE_MODE:
        errors.append("migration Candidate provenance_mode mismatch")
    if candidate.get("canonical_write_performed") is not False:
        errors.append("canonical_write_performed must remain false")
    if candidate.get("boundary") != CHANGE_CANDIDATE_MIGRATION_BOUNDARY:
        errors.append("Candidate migration boundary mismatch")

    if not isinstance(source_ids, list) or any(not isinstance(item, str) or not item for item in source_ids):
        errors.append("predecessor source_ids must be an array of non-empty strings")
    else:
        missing = sorted(set(source_ids) - known_source_ids)
        if missing:
            errors.append(f"change candidate references missing Sources {missing}")

    schema_errors = validate_graph_object(
        {key: value for key, value in candidate.items() if key != "canonical_sha256"},
        "Candidate",
    )
    errors.extend(f"schema: {error}" for error in schema_errors)
    return sorted(set(errors))


def materialize_v16_change_candidate(
    record: dict[str, Any],
    *,
    record_index: int,
    known_source_ids: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Materialize one exact v1.6 change-candidate record as a native Candidate."""
    if not isinstance(record, dict):
        raise ObservatoryChangeCandidateMigrationError("change candidate must be an object")
    required_strings = ("candidate_id", "change_class", "adjudication")
    missing = [
        field for field in required_strings if not isinstance(record.get(field), str) or not str(record[field]).strip()
    ]
    if missing:
        raise ObservatoryChangeCandidateMigrationError(
            f"change candidate missing required predecessor fields: {missing}"
        )
    source_ids = record.get("source_ids")
    if not isinstance(source_ids, list) or any(not isinstance(item, str) or not item for item in source_ids):
        raise ObservatoryChangeCandidateMigrationError(
            "change candidate source_ids must be an array of non-empty strings"
        )
    missing_sources = sorted(set(source_ids) - known_source_ids)
    if missing_sources:
        raise ObservatoryChangeCandidateMigrationError(
            f"change candidate references non-materialized Sources {missing_sources}"
        )

    candidate = build_candidate(
        candidate_id=str(record["candidate_id"]),
        candidate_class=str(record["change_class"]),
        payload=dict(record),
        provenance_mode=MIGRATION_PROVENANCE_MODE,
        status=str(record["adjudication"]),
        boundary=CHANGE_CANDIDATE_MIGRATION_BOUNDARY,
    )
    trace = {
        "role": "V16",
        "family": "change_candidates",
        "record_index": record_index,
        "native_object_class": "Candidate",
        "native_object_id": str(candidate["candidate_id"]),
        "predecessor_record_sha256": _record_digest(record),
        "predecessor_record": record,
        "migration_generated_fields": {
            "provenance_mode": MIGRATION_PROVENANCE_MODE,
            "canonical_write_performed": False,
        },
        "native_authority": False,
        "boundary": CHANGE_CANDIDATE_MIGRATION_BOUNDARY,
    }
    errors = verify_change_candidate_trace(candidate, trace, known_source_ids=known_source_ids)
    if errors:
        raise ObservatoryChangeCandidateMigrationError(f"generated change Candidate/trace is invalid: {errors}")
    return candidate, trace


def materialize_v16_change_candidates(
    v16_refresh: dict[str, Any],
    *,
    known_source_ids: set[str],
) -> dict[str, Any]:
    """Materialize the complete v1.6 change-candidate family or fail closed."""
    records = v16_refresh.get("change_candidates")
    if not isinstance(records, list):
        raise ObservatoryChangeCandidateMigrationError("Expected v1.6 change_candidates array")
    candidates: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            raise ObservatoryChangeCandidateMigrationError(f"v1.6 change candidate {index} must be an object")
        candidate, trace = materialize_v16_change_candidate(
            raw,
            record_index=index,
            known_source_ids=known_source_ids,
        )
        candidate_id = str(candidate["candidate_id"])
        if candidate_id in seen_ids:
            raise ObservatoryChangeCandidateMigrationError(f"duplicate predecessor change candidate id {candidate_id}")
        seen_ids.add(candidate_id)
        candidates.append(candidate)
        traces.append(trace)
    return {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "object_class": "Candidate",
        "input_record_count": len(records),
        "object_count": len(candidates),
        "predecessor_trace_count": len(traces),
        "candidates": candidates,
        "predecessor_traces": traces,
        "migration_generated_metadata": {
            "provenance_mode": MIGRATION_PROVENANCE_MODE,
            "canonical_write_performed": False,
            "boundary": CHANGE_CANDIDATE_MIGRATION_BOUNDARY,
        },
        "boundary": CHANGE_CANDIDATE_MIGRATION_BOUNDARY,
    }


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for record in records]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def write_change_candidate_migration_package(
    result: dict[str, Any],
    output_dir: Path,
    *,
    known_source_ids: set[str],
    v16_input_sha256: str,
    producer_commit: str,
    runtime_execution_pin: str,
    s2_predecessor_commit: str,
    observatory_graph_schema_version: str = "1",
) -> dict[str, Any]:
    """Write a deterministic package for the complete v1.6 change-candidate family."""
    if result.get("state") != "NONCANONICAL_CANDIDATE" or result.get("release_authorized") is not False:
        raise ObservatoryChangeCandidateMigrationError("change-candidate migration package must remain noncanonical")
    candidates = result.get("candidates")
    traces = result.get("predecessor_traces")
    if not isinstance(candidates, list) or not isinstance(traces, list) or len(candidates) != len(traces):
        raise ObservatoryChangeCandidateMigrationError("change-candidate package requires one trace per Candidate")
    if result.get("input_record_count") != len(candidates):
        raise ObservatoryChangeCandidateMigrationError(
            "change-candidate package requires complete family materialization"
        )
    for candidate, trace in zip(candidates, traces, strict=True):
        if not isinstance(candidate, dict) or not isinstance(trace, dict):
            raise ObservatoryChangeCandidateMigrationError("change-candidate package entries must be objects")
        errors = verify_change_candidate_trace(candidate, trace, known_source_ids=known_source_ids)
        if errors:
            raise ObservatoryChangeCandidateMigrationError(f"change-candidate verification failed: {errors}")

    input_v16 = _require_hex(v16_input_sha256, length=64, field="v16_input_sha256")
    producer = _require_hex(producer_commit, length=40, field="producer_commit")
    runtime_pin = _require_hex(runtime_execution_pin, length=40, field="runtime_execution_pin")
    s2_commit = _require_hex(s2_predecessor_commit, length=40, field="s2_predecessor_commit")
    if not isinstance(observatory_graph_schema_version, str) or not observatory_graph_schema_version.strip():
        raise ObservatoryChangeCandidateMigrationError("observatory_graph_schema_version must be non-empty")

    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_bytes = _jsonl_bytes(candidates)
    trace_bytes = _jsonl_bytes(traces)
    atomic_write_bytes(output_dir / "candidates.jsonl", candidate_bytes)
    atomic_write_bytes(output_dir / "predecessor-traces.jsonl", trace_bytes)
    file_digests = {
        "candidates.jsonl": sha256_bytes(candidate_bytes),
        "predecessor-traces.jsonl": sha256_bytes(trace_bytes),
    }
    descriptor = {
        "schema_version": "1",
        "package_type": "OBSERVATORY_V2_PREDECESSOR_CHANGE_CANDIDATE_MIGRATION",
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "object_count": len(candidates),
        "workbench_compatibility_version": __version__,
        "producer_workbench_commit": producer,
        "runtime_execution_pin": runtime_pin,
        "observatory_graph_schema_version": observatory_graph_schema_version,
        "s2_predecessor_commit": s2_commit,
        "inputs": {"V16": input_v16},
        "migration_generated_metadata": result.get("migration_generated_metadata"),
        "boundary": CHANGE_CANDIDATE_MIGRATION_BOUNDARY,
    }
    manifest = {
        "files": [{"path": path, "sha256": digest} for path, digest in sorted(file_digests.items())],
        "descriptor_sha256": sha256_bytes(canonical_json_bytes(descriptor)),
        "release_authorized": False,
        "boundary": CHANGE_CANDIDATE_MIGRATION_BOUNDARY,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    atomic_write_json(output_dir / "descriptor.json", descriptor)
    atomic_write_json(output_dir / "manifest.json", manifest)
    return {"descriptor": descriptor, "manifest": manifest}
