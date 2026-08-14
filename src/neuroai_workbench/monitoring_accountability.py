from __future__ import annotations

from collections import Counter
from typing import Any

from .util import canonical_json_bytes, sha256_bytes

ACCOUNTABILITY_STATES = frozenset({"MANUAL_ONLY", "EXEMPT_WITH_RATIONALE"})
BOUNDARY = (
    "Monitoring-accountability reconciliation classifies every declared effective source against exact monitoring "
    "or explicit non-monitor scope records. It does not establish source truth, open-world completeness, assessment "
    "validity, regulatory or clinical status, governance approval, UNESCO endorsement, or release authority."
)


def _hash(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _source_id(record: Any, *, label: str) -> str:
    if isinstance(record, str):
        value = record.strip()
    elif isinstance(record, dict):
        value = str(record.get("source_id", "")).strip()
    else:
        raise ValueError(f"{label} must be a source ID string or object")
    if not value:
        raise ValueError(f"{label} is missing source_id")
    return value


def _index_unique(records: list[Any], *, label: str) -> tuple[dict[str, Any], list[str]]:
    index: dict[str, Any] = {}
    duplicates: list[str] = []
    for offset, record in enumerate(records):
        source_id = _source_id(record, label=f"{label}[{offset}]")
        if source_id in index:
            duplicates.append(source_id)
        else:
            index[source_id] = record
    return index, sorted(set(duplicates))


def _normalize_non_monitor_record(record: Any, *, offset: int) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError(f"accountability[{offset}] must be an object")
    source_id = _source_id(record, label=f"accountability[{offset}]")
    state = str(record.get("accountability_state", "")).strip()
    if state not in ACCOUNTABILITY_STATES:
        raise ValueError(f"accountability[{offset}] has unsupported accountability_state {state!r}")
    rationale = str(record.get("rationale", "")).strip()
    if not rationale:
        raise ValueError(f"accountability[{offset}] requires rationale")
    normalized: dict[str, Any] = {
        "source_id": source_id,
        "accountability_state": state,
        "rationale": rationale,
    }
    supporting_record_id = str(record.get("supporting_record_id", "")).strip()
    supporting_sha256 = str(record.get("supporting_sha256", "")).strip()
    if supporting_record_id:
        normalized["supporting_record_id"] = supporting_record_id
    if supporting_sha256:
        if len(supporting_sha256) != 64 or any(character not in "0123456789abcdef" for character in supporting_sha256):
            raise ValueError(f"accountability[{offset}].supporting_sha256 must be lowercase SHA-256")
        normalized["supporting_sha256"] = supporting_sha256
    return normalized


def evaluate_monitoring_accountability(
    *,
    effective_sources: list[Any],
    monitor_registry: list[Any],
    non_monitor_accountability: list[Any] | None = None,
) -> dict[str, Any]:
    """Reconcile an effective source namespace to one explicit operational accountability state."""
    non_monitor_accountability = non_monitor_accountability or []
    effective_index, duplicate_effective = _index_unique(effective_sources, label="effective_sources")
    monitor_index, duplicate_monitor_sources = _index_unique(monitor_registry, label="monitor_registry")

    normalized_non_monitor = [
        _normalize_non_monitor_record(record, offset=offset) for offset, record in enumerate(non_monitor_accountability)
    ]
    non_monitor_index, duplicate_non_monitor_sources = _index_unique(
        normalized_non_monitor,
        label="accountability",
    )

    effective_ids = set(effective_index)
    monitor_ids = set(monitor_index)
    non_monitor_ids = set(non_monitor_index)
    orphan_monitor_ids = sorted(monitor_ids - effective_ids)
    orphan_accountability_ids = sorted(non_monitor_ids - effective_ids)
    ambiguous_ids = sorted(monitor_ids & non_monitor_ids & effective_ids)

    rows: list[dict[str, Any]] = []
    gaps: list[str] = []
    counts: Counter[str] = Counter()
    for source_id in sorted(effective_ids):
        if source_id in ambiguous_ids:
            state = "AMBIGUOUS"
            row = {
                "source_id": source_id,
                "accountability_state": state,
                "monitor_id": (
                    monitor_index[source_id].get("monitor_id") if isinstance(monitor_index[source_id], dict) else None
                ),
                "non_monitor_record": non_monitor_index[source_id],
            }
        elif source_id in monitor_index:
            state = "MONITORED"
            monitor = monitor_index[source_id]
            row = {
                "source_id": source_id,
                "accountability_state": state,
                "monitor_id": monitor.get("monitor_id") if isinstance(monitor, dict) else None,
                "monitor_record_sha256": _hash(monitor),
            }
        elif source_id in non_monitor_index:
            record = non_monitor_index[source_id]
            state = str(record["accountability_state"])
            row = {
                "source_id": source_id,
                "accountability_state": state,
                "rationale": record["rationale"],
                "accountability_record_sha256": _hash(record),
            }
            if record.get("supporting_record_id"):
                row["supporting_record_id"] = record["supporting_record_id"]
            if record.get("supporting_sha256"):
                row["supporting_sha256"] = record["supporting_sha256"]
        else:
            state = "GAP"
            gaps.append(source_id)
            row = {"source_id": source_id, "accountability_state": state}
        counts[state] += 1
        rows.append(row)

    errors: list[str] = []
    for source_id in duplicate_effective:
        errors.append(f"duplicate effective source ID: {source_id}")
    for source_id in duplicate_monitor_sources:
        errors.append(f"multiple monitor records for source: {source_id}")
    for source_id in duplicate_non_monitor_sources:
        errors.append(f"multiple non-monitor accountability records for source: {source_id}")
    for source_id in orphan_monitor_ids:
        errors.append(f"orphan monitor source ID: {source_id}")
    for source_id in orphan_accountability_ids:
        errors.append(f"orphan accountability source ID: {source_id}")
    for source_id in ambiguous_ids:
        errors.append(f"source has monitor and non-monitor accountability simultaneously: {source_id}")
    for source_id in gaps:
        errors.append(f"monitoring accountability gap: {source_id}")

    effective_count = len(effective_ids)
    accounted_count = effective_count - len(gaps) - len(ambiguous_ids)
    input_binding = {
        "effective_sources_sha256": _hash(effective_sources),
        "monitor_registry_sha256": _hash(monitor_registry),
        "non_monitor_accountability_sha256": _hash(normalized_non_monitor),
    }
    report: dict[str, Any] = {
        "schema_version": "1",
        "input_binding": input_binding,
        "counts": {
            "effective_sources": effective_count,
            "monitor_registry_records": len(monitor_registry),
            "non_monitor_accountability_records": len(normalized_non_monitor),
            "MONITORED": counts["MONITORED"],
            "MANUAL_ONLY": counts["MANUAL_ONLY"],
            "EXEMPT_WITH_RATIONALE": counts["EXEMPT_WITH_RATIONALE"],
            "GAP": counts["GAP"],
            "AMBIGUOUS": counts["AMBIGUOUS"],
            "orphan_monitors": len(orphan_monitor_ids),
            "orphan_accountability": len(orphan_accountability_ids),
            "duplicate_effective_sources": len(duplicate_effective),
            "duplicate_monitor_sources": len(duplicate_monitor_sources),
            "duplicate_non_monitor_sources": len(duplicate_non_monitor_sources),
        },
        "coverage_fraction": 1.0 if effective_count == 0 else accounted_count / effective_count,
        "complete": not errors,
        "gap_source_ids": gaps,
        "ambiguous_source_ids": ambiguous_ids,
        "orphan_monitor_source_ids": orphan_monitor_ids,
        "orphan_accountability_source_ids": orphan_accountability_ids,
        "duplicate_effective_source_ids": duplicate_effective,
        "duplicate_monitor_source_ids": duplicate_monitor_sources,
        "duplicate_non_monitor_source_ids": duplicate_non_monitor_sources,
        "sources": rows,
        "errors": errors,
        "boundary": BOUNDARY,
    }
    report["report_sha256"] = _hash(report)
    return report


def verify_monitoring_accountability_report(
    report: dict[str, Any],
    *,
    effective_sources: list[Any],
    monitor_registry: list[Any],
    non_monitor_accountability: list[Any] | None = None,
) -> dict[str, Any]:
    """Recompute the report and detect substitution or tampering."""
    expected = evaluate_monitoring_accountability(
        effective_sources=effective_sources,
        monitor_registry=monitor_registry,
        non_monitor_accountability=non_monitor_accountability,
    )
    errors: list[str] = []
    if report.get("report_sha256") != _hash({key: value for key, value in report.items() if key != "report_sha256"}):
        errors.append("recorded report hash mismatch")
    if canonical_json_bytes(report) != canonical_json_bytes(expected):
        errors.append("report does not match recomputed accountability projection")
    return {
        "valid": not errors,
        "errors": errors,
        "complete": report.get("complete") is True and not errors,
        "coverage_fraction": report.get("coverage_fraction"),
        "boundary": BOUNDARY,
    }
