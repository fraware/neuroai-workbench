"""Loss-aware predecessor materialization for Observatory v2 migration candidates.

Native objects produced here remain noncanonical migration output. Every materialized
record retains an exact content-addressed predecessor trace so normalization cannot
silently discard predecessor semantics that are not represented by the native schema.
"""

from __future__ import annotations

import re
from typing import Any

from .observatory_graph import build_source, validate_graph_object
from .temporal import TIME_VALUE_BOUNDARY, parse_time_value
from .util import canonical_json_bytes, sha256_bytes

MIGRATION_BOUNDARY = (
    "Migrated predecessor source identity only. UNKNOWN access and redistribution states are controlled "
    "migration metadata, not inferred source rights. Native normalization does not upgrade predecessor "
    "evidence, verification, claim-boundary, currentness, or publication authority."
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_YEAR_RE = re.compile(r"^\d{4}$")
_SOURCE_FAMILY_BY_ROLE = {"V14": "sources", "V16": "new_sources"}


class ObservatoryMigrationError(ValueError):
    """Raised when predecessor state cannot be materialized without ambiguity or invention."""


def predecessor_time_value(value: Any) -> dict[str, Any] | None:
    """Map an explicit predecessor date/time literal without increasing precision.

    Missing values remain missing. YEAR and DATE literals are preserved at their
    original precision. Timestamp literals require an explicit timezone through the
    ordinary TimeValue parser.
    """
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ObservatoryMigrationError("Predecessor temporal value must be a string or null")
    text = value.strip()
    if _YEAR_RE.fullmatch(text):
        precision = "YEAR"
    elif _DATE_RE.fullmatch(text):
        precision = "DATE"
    elif "T" in text:
        precision = "TIMESTAMP"
    else:
        raise ObservatoryMigrationError(f"Unsupported predecessor temporal literal {value!r}")
    return parse_time_value({"value": text, "precision": precision, "boundary": TIME_VALUE_BOUNDARY})


def predecessor_trace(
    *,
    role: str,
    family: str,
    record_index: int,
    record: dict[str, Any],
    native_object_id: str,
) -> dict[str, Any]:
    """Return the exact predecessor record and digest used for lossless traceability."""
    return {
        "role": role,
        "family": family,
        "record_index": record_index,
        "native_object_id": native_object_id,
        "predecessor_record_sha256": sha256_bytes(canonical_json_bytes(record)),
        "predecessor_record": record,
        "native_authority": False,
        "boundary": MIGRATION_BOUNDARY,
    }


def verify_predecessor_trace(
    trace: dict[str, Any],
    *,
    expected_native_object_id: str | None = None,
) -> list[str]:
    """Independently verify predecessor-byte identity and native-object binding."""
    errors: list[str] = []
    record = trace.get("predecessor_record")
    if not isinstance(record, dict):
        errors.append("predecessor_record must be an object")
    else:
        observed = sha256_bytes(canonical_json_bytes(record))
        if trace.get("predecessor_record_sha256") != observed:
            errors.append("predecessor_record_sha256 mismatch")
    if trace.get("native_authority") is not False:
        errors.append("native_authority must remain false for migration traces")
    if trace.get("boundary") != MIGRATION_BOUNDARY:
        errors.append("migration trace boundary mismatch")
    role = str(trace.get("role") or "")
    expected_family = _SOURCE_FAMILY_BY_ROLE.get(role)
    if expected_family is None:
        errors.append(f"unsupported migration trace role {role!r}")
    elif trace.get("family") != expected_family:
        errors.append("migration trace family/role mismatch")
    if not isinstance(trace.get("record_index"), int) or int(trace["record_index"]) < 0:
        errors.append("record_index must be a non-negative integer")
    native_object_id = trace.get("native_object_id")
    if not isinstance(native_object_id, str) or not native_object_id:
        errors.append("native_object_id must be a non-empty string")
    if expected_native_object_id is not None and native_object_id != expected_native_object_id:
        errors.append("native_object_id binding mismatch")
    return errors


def materialize_predecessor_source(
    record: dict[str, Any],
    *,
    role: str,
    record_index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Materialize one v1.4/v1.6 predecessor source into a schema-valid v2 Source.

    `retrieved` is deliberately not mapped to `publication_or_record_date`; it is
    knowledge-time evidence and would require a separate Observation migration.
    Only the explicit v1.6 `published` field may populate source publication time.
    """
    family = _SOURCE_FAMILY_BY_ROLE.get(role)
    if family is None:
        raise ObservatoryMigrationError(f"Unsupported predecessor source role {role!r}")

    required = ("source_id", "source_class", "title", "publisher", "url")
    missing = [
        field
        for field in required
        if not isinstance(record.get(field), str) or not str(record[field]).strip()
    ]
    if missing:
        raise ObservatoryMigrationError(f"Source record is missing required predecessor fields: {missing}")

    publication = predecessor_time_value(record.get("published"))
    source = build_source(
        source_id=str(record["source_id"]),
        source_class=str(record["source_class"]),
        title=str(record["title"]),
        publisher=str(record["publisher"]),
        canonical_url_or_reference=str(record["url"]),
        access_class="UNKNOWN",
        redistribution_state="UNKNOWN_NOT_ADJUDICATED",
        publication_or_record_date=publication,
        boundary=MIGRATION_BOUNDARY,
    )
    errors = validate_graph_object(
        {key: value for key, value in source.items() if key != "canonical_sha256"},
        "Source",
    )
    if errors:
        raise ObservatoryMigrationError(f"Materialized Source is schema-invalid: {errors}")
    trace = predecessor_trace(
        role=role,
        family=family,
        record_index=record_index,
        record=record,
        native_object_id=str(source["source_id"]),
    )
    trace_errors = verify_predecessor_trace(trace, expected_native_object_id=str(source["source_id"]))
    if trace_errors:
        raise ObservatoryMigrationError(f"Generated predecessor trace is invalid: {trace_errors}")
    return source, trace


def materialize_predecessor_sources(
    *,
    v14_release: dict[str, Any],
    v16_refresh: dict[str, Any],
) -> dict[str, Any]:
    """Materialize exact v1.4 sources plus v1.6 new sources with no silent overwrite."""
    v14_sources = v14_release.get("sources")
    v16_sources = v16_refresh.get("new_sources")
    if not isinstance(v14_sources, list) or not isinstance(v16_sources, list):
        raise ObservatoryMigrationError("Expected v1.4 sources and v1.6 new_sources arrays")

    native_sources: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    seen: set[str] = set()
    for role, records in (("V14", v14_sources), ("V16", v16_sources)):
        for index, raw in enumerate(records):
            if not isinstance(raw, dict):
                raise ObservatoryMigrationError(f"{role} source record {index} must be an object")
            source, trace = materialize_predecessor_source(raw, role=role, record_index=index)
            source_id = str(source["source_id"])
            if source_id in seen:
                raise ObservatoryMigrationError(f"Duplicate predecessor source id {source_id}")
            seen.add(source_id)
            native_sources.append(source)
            traces.append(trace)

    return {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "object_class": "Source",
        "object_count": len(native_sources),
        "predecessor_trace_count": len(traces),
        "sources": native_sources,
        "predecessor_traces": traces,
        "migration_generated_metadata": {
            "access_class": "UNKNOWN",
            "redistribution_state": "UNKNOWN_NOT_ADJUDICATED",
            "boundary": MIGRATION_BOUNDARY,
        },
        "retrieved_not_promoted_to_publication_time": True,
        "boundary": MIGRATION_BOUNDARY,
    }
