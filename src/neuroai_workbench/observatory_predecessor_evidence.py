"""Migration-only representation for predecessor observation evidence.

The v1.6 source-check records contain governed knowledge-time evidence but do not
record all transport facts required by an ordinary Observatory-v2 Observation.
This module preserves those records exactly and marks the missing transport facts as
unresolved. It deliberately does not create a native Observation by inventing a
retrieval method or requested locator.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from . import __version__
from .temporal import TIME_VALUE_BOUNDARY, parse_time_value
from .util import atomic_write_bytes, atomic_write_json, canonical_json_bytes, sha256_bytes

PREDECESSOR_OBSERVATION_BOUNDARY = (
    "Predecessor observation evidence preserves exact v1.6 source-check state. Missing transport provenance "
    "remains explicitly unresolved; no HTTP method, request URL, content capture, or substantive success is "
    "manufactured. This sidecar is noncanonical migration evidence and is not an ordinary v2 Observation."
)
PREDECESSOR_OBSERVATION_TRANSPORT_UNRESOLVED = "PREDECESSOR_OBSERVATION_TRANSPORT_UNRESOLVED"
UNRESOLVED_TRANSPORT_FIELDS = ("retrieval_method", "requested_locator")
EXPECTED_PREDECESSOR_FIELDS = frozenset(
    {
        "check_id",
        "source_id",
        "retrieved",
        "retrieval_outcome",
        "baseline_match",
        "page_content_hash",
        "metadata_digest",
    }
)


class PredecessorObservationEvidenceError(ValueError):
    """Raised when predecessor source-check evidence is malformed or silently completed."""


def _require_hex(value: Any, *, length: int, field: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(char not in "0123456789abcdef" for char in value):
        raise PredecessorObservationEvidenceError(
            f"{field} must be a lowercase {length}-character hexadecimal identity"
        )
    return value


def _record_digest(record: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(record))


def _observed_at(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        raise PredecessorObservationEvidenceError("source check requires an explicit retrieved timestamp")
    text = value.strip()
    return parse_time_value({"value": text, "precision": "TIMESTAMP", "boundary": TIME_VALUE_BOUNDARY})


def preserve_source_check(record: dict[str, Any], *, record_index: int) -> dict[str, Any]:
    """Preserve one v1.6 source check without manufacturing native Observation fields."""
    if not isinstance(record, dict):
        raise PredecessorObservationEvidenceError("source check must be an object")
    unknown = sorted(set(record) - EXPECTED_PREDECESSOR_FIELDS)
    missing = sorted(EXPECTED_PREDECESSOR_FIELDS - set(record))
    if unknown:
        raise PredecessorObservationEvidenceError(f"unreviewed source-check fields: {unknown}")
    if missing:
        raise PredecessorObservationEvidenceError(f"source-check fields missing: {missing}")

    check_id = record.get("check_id")
    source_id = record.get("source_id")
    retrieval_outcome = record.get("retrieval_outcome")
    metadata_digest = record.get("metadata_digest")
    if not isinstance(check_id, str) or not check_id.strip():
        raise PredecessorObservationEvidenceError("source check requires non-empty check_id")
    if not isinstance(source_id, str) or not source_id.strip():
        raise PredecessorObservationEvidenceError("source check requires non-empty source_id")
    if not isinstance(retrieval_outcome, str) or not retrieval_outcome.strip():
        raise PredecessorObservationEvidenceError("source check requires predecessor retrieval_outcome")
    _require_hex(metadata_digest, length=64, field="metadata_digest")

    evidence = {
        "role": "V16",
        "family": "source_checks",
        "record_index": record_index,
        "migration_state": PREDECESSOR_OBSERVATION_TRANSPORT_UNRESOLVED,
        "predecessor_check_id": check_id,
        "source_id": source_id,
        "observed_at": _observed_at(record.get("retrieved")),
        "predecessor_retrieval_outcome": retrieval_outcome,
        "unresolved_native_observation_fields": list(UNRESOLVED_TRANSPORT_FIELDS),
        "native_observation_created": False,
        "predecessor_record_sha256": _record_digest(record),
        "predecessor_record": record,
        "native_authority": False,
        "boundary": PREDECESSOR_OBSERVATION_BOUNDARY,
    }
    errors = verify_preserved_source_check(evidence)
    if errors:
        raise PredecessorObservationEvidenceError(f"generated predecessor observation evidence is invalid: {errors}")
    return evidence


def verify_preserved_source_check(evidence: dict[str, Any]) -> list[str]:
    """Verify exact predecessor identity and the prohibition on invented transport completion."""
    errors: list[str] = []
    record = evidence.get("predecessor_record")
    if not isinstance(record, dict):
        return ["predecessor_record must be an object"]

    if set(record) != EXPECTED_PREDECESSOR_FIELDS:
        errors.append("predecessor source-check field set mismatch")
    if evidence.get("predecessor_record_sha256") != _record_digest(record):
        errors.append("predecessor_record_sha256 mismatch")
    if evidence.get("role") != "V16" or evidence.get("family") != "source_checks":
        errors.append("predecessor observation role/family mismatch")
    if evidence.get("migration_state") != PREDECESSOR_OBSERVATION_TRANSPORT_UNRESOLVED:
        errors.append("predecessor observation migration_state mismatch")
    if evidence.get("native_observation_created") is not False:
        errors.append("native_observation_created must remain false")
    if evidence.get("native_authority") is not False:
        errors.append("native_authority must remain false")
    if evidence.get("boundary") != PREDECESSOR_OBSERVATION_BOUNDARY:
        errors.append("predecessor observation boundary mismatch")
    if evidence.get("unresolved_native_observation_fields") != list(UNRESOLVED_TRANSPORT_FIELDS):
        errors.append("unresolved transport field set mismatch")
    if any(field in evidence for field in UNRESOLVED_TRANSPORT_FIELDS):
        errors.append("unresolved transport fields must not be populated in migration evidence")
    if not isinstance(evidence.get("record_index"), int) or int(evidence["record_index"]) < 0:
        errors.append("record_index must be a non-negative integer")

    if evidence.get("predecessor_check_id") != record.get("check_id"):
        errors.append("predecessor_check_id binding mismatch")
    if evidence.get("source_id") != record.get("source_id"):
        errors.append("source_id binding mismatch")
    if evidence.get("predecessor_retrieval_outcome") != record.get("retrieval_outcome"):
        errors.append("predecessor retrieval outcome binding mismatch")
    try:
        expected_time = _observed_at(record.get("retrieved"))
        if evidence.get("observed_at") != expected_time:
            errors.append("observed_at binding mismatch")
    except (PredecessorObservationEvidenceError, ValueError) as exc:
        errors.append(str(exc))

    try:
        _require_hex(record.get("metadata_digest"), length=64, field="metadata_digest")
    except PredecessorObservationEvidenceError as exc:
        errors.append(str(exc))
    return sorted(set(errors))


def preserve_v16_source_checks(v16_refresh: dict[str, Any], *, known_source_ids: set[str]) -> dict[str, Any]:
    """Preserve every v1.6 source check and bind each to an already materialized predecessor Source id."""
    records = v16_refresh.get("source_checks")
    if not isinstance(records, list):
        raise PredecessorObservationEvidenceError("Expected v1.6 source_checks array")
    if not isinstance(known_source_ids, set) or any(not isinstance(item, str) or not item for item in known_source_ids):
        raise PredecessorObservationEvidenceError("known_source_ids must be a set of non-empty strings")

    evidence_records: list[dict[str, Any]] = []
    seen_checks: set[str] = set()
    seen_sources: Counter[str] = Counter()
    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            raise PredecessorObservationEvidenceError(f"v1.6 source check {index} must be an object")
        evidence = preserve_source_check(raw, record_index=index)
        check_id = str(evidence["predecessor_check_id"])
        source_id = str(evidence["source_id"])
        if check_id in seen_checks:
            raise PredecessorObservationEvidenceError(f"duplicate predecessor check_id {check_id}")
        seen_checks.add(check_id)
        seen_sources[source_id] += 1
        if source_id not in known_source_ids:
            raise PredecessorObservationEvidenceError(
                f"predecessor source check {check_id} references non-materialized Source {source_id}"
            )
        evidence_records.append(evidence)

    duplicate_sources = sorted(source_id for source_id, count in seen_sources.items() if count > 1)
    if duplicate_sources:
        raise PredecessorObservationEvidenceError(
            f"multiple predecessor source checks reference the same Source ids: {duplicate_sources}"
        )

    return {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "native_observation_count": 0,
        "predecessor_observation_evidence_count": len(evidence_records),
        "transport_unresolved_count": len(evidence_records),
        "records": evidence_records,
        "boundary": PREDECESSOR_OBSERVATION_BOUNDARY,
    }


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for record in records]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def write_predecessor_observation_evidence_package(
    result: dict[str, Any],
    output_dir: Path,
    *,
    v16_input_sha256: str,
    producer_commit: str,
    runtime_execution_pin: str,
    s2_predecessor_commit: str,
    observatory_graph_schema_version: str = "1",
) -> dict[str, Any]:
    """Write a deterministic package for transport-unresolved predecessor observation evidence."""
    records = result.get("records")
    if not isinstance(records, list):
        raise PredecessorObservationEvidenceError("predecessor observation package requires records list")
    if result.get("state") != "NONCANONICAL_CANDIDATE" or result.get("release_authorized") is not False:
        raise PredecessorObservationEvidenceError("predecessor observation package must remain noncanonical")
    if result.get("native_observation_count") != 0:
        raise PredecessorObservationEvidenceError("transport-unresolved evidence cannot claim native Observations")
    for record in records:
        if not isinstance(record, dict):
            raise PredecessorObservationEvidenceError("predecessor observation evidence records must be objects")
        errors = verify_preserved_source_check(record)
        if errors:
            raise PredecessorObservationEvidenceError(f"predecessor observation evidence verification failed: {errors}")

    input_v16 = _require_hex(v16_input_sha256, length=64, field="v16_input_sha256")
    producer = _require_hex(producer_commit, length=40, field="producer_commit")
    runtime_pin = _require_hex(runtime_execution_pin, length=40, field="runtime_execution_pin")
    s2_commit = _require_hex(s2_predecessor_commit, length=40, field="s2_predecessor_commit")
    if not isinstance(observatory_graph_schema_version, str) or not observatory_graph_schema_version.strip():
        raise PredecessorObservationEvidenceError("observatory_graph_schema_version must be non-empty")

    output_dir.mkdir(parents=True, exist_ok=True)
    record_bytes = _jsonl_bytes(records)
    atomic_write_bytes(output_dir / "predecessor-observation-evidence.jsonl", record_bytes)
    file_digest = sha256_bytes(record_bytes)
    descriptor = {
        "schema_version": "1",
        "package_type": "OBSERVATORY_V2_PREDECESSOR_OBSERVATION_EVIDENCE",
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "native_observation_count": 0,
        "predecessor_observation_evidence_count": len(records),
        "transport_unresolved_count": len(records),
        "workbench_compatibility_version": __version__,
        "producer_workbench_commit": producer,
        "runtime_execution_pin": runtime_pin,
        "observatory_graph_schema_version": observatory_graph_schema_version,
        "s2_predecessor_commit": s2_commit,
        "inputs": {"V16": input_v16},
        "unresolved_native_observation_fields": list(UNRESOLVED_TRANSPORT_FIELDS),
        "boundary": PREDECESSOR_OBSERVATION_BOUNDARY,
    }
    manifest = {
        "files": [{"path": "predecessor-observation-evidence.jsonl", "sha256": file_digest}],
        "descriptor_sha256": sha256_bytes(canonical_json_bytes(descriptor)),
        "release_authorized": False,
        "boundary": PREDECESSOR_OBSERVATION_BOUNDARY,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    atomic_write_json(output_dir / "descriptor.json", descriptor)
    atomic_write_json(output_dir / "manifest.json", manifest)
    return {"descriptor": descriptor, "manifest": manifest}
