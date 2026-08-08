"""Read-only observatory data-health and freshness diagnostics."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .util import atomic_write_json

CADENCE_DAYS = {
    "DAILY": 1,
    "WEEKLY": 7,
    "BIWEEKLY": 14,
    "MONTHLY": 31,
    "QUARTERLY": 92,
    "SEMIANNUAL": 183,
    "ANNUAL": 366,
    "YEARLY": 366,
}
ATTENTION_TOKENS = ("UNRESOLVED", "UNKNOWN", "PARTIAL", "MISSING", "NOT_VERIFIED")
ID_FIELDS = (
    "organization_id",
    "source_id",
    "monitor_id",
    "model_id",
    "event_id",
    "dependency_id",
    "decision_id",
    "assessment_id",
    "id",
)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    token = value.strip()
    try:
        return date.fromisoformat(token[:10])
    except ValueError:
        try:
            return datetime.fromisoformat(token.replace("Z", "+00:00")).date()
        except ValueError:
            return None


def as_of_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    parsed = parse_date(value)
    if parsed is None:
        raise ValueError(f"Invalid as-of date: {value!r}")
    return parsed


def normalize_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw.casefold().rstrip("/")
    if not parsed.scheme or not parsed.netloc:
        return raw.casefold().rstrip("/")
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), path, parsed.query, ""))


def registry_records(registry: Any) -> list[dict[str, Any]]:
    if isinstance(registry, list):
        return [item for item in registry if isinstance(item, dict)]
    if isinstance(registry, dict) and isinstance(registry.get("sources"), list):
        return [item for item in registry["sources"] if isinstance(item, dict)]
    raise ValueError("Source registry must be a list or an object containing sources")


def _distribution(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts = Counter(str(record.get(field) or "MISSING") for record in records)
    return dict(sorted(counts.items()))


def _completeness(records: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, dict[str, float | int]]:
    total = len(records)
    result: dict[str, dict[str, float | int]] = {}
    for field in fields:
        present = sum(
            1
            for record in records
            if record.get(field) is not None and record.get(field) != "" and record.get(field) != []
        )
        result[field] = {
            "present": present,
            "missing": total - present,
            "rate": round(present / total, 4) if total else 0.0,
        }
    return result


def _duplicates(records: list[dict[str, Any]], field: str, *, urls: bool = False) -> list[dict[str, Any]]:
    seen: dict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        raw = record.get(field)
        value = normalize_url(raw) if urls else (str(raw).strip() if raw is not None else None)
        if value:
            seen[value].append(index)
    return [
        {"value": value, "count": len(indexes), "record_indexes": indexes}
        for value, indexes in sorted(seen.items())
        if len(indexes) > 1
    ]


def _attention_states(records: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        record_id = next((record.get(field) for field in ID_FIELDS if record.get(field)), None)
        for field in fields:
            value = record.get(field)
            token = str(value or "").upper()
            if any(marker in token for marker in ATTENTION_TOKENS):
                rows.append({"record_id": record_id, "field": field, "value": value})
    return rows


def profile_registry(registry: Any, *, as_of: str | date) -> dict[str, Any]:
    records = registry_records(registry)
    day = as_of_date(as_of)
    freshness: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for record in records:
        cadence = str(record.get("cadence") or "UNRESOLVED").upper()
        interval = CADENCE_DAYS.get(cadence)
        retrieved = parse_date(record.get("last_successful_retrieval"))
        age: int | None = None
        if retrieved is None:
            state = "NEVER_OR_INVALID"
        elif retrieved > day:
            age = (day - retrieved).days
            state = "FUTURE_DATE"
        else:
            age = (day - retrieved).days
            if interval is None:
                state = "UNKNOWN_CADENCE"
            elif age <= interval:
                state = "CURRENT"
            elif age <= interval * 2:
                state = "DUE"
            else:
                state = "STALE"
        counts[state] += 1
        freshness.append(
            {
                "source_id": record.get("source_id"),
                "publisher": record.get("publisher"),
                "source_class": record.get("source_class"),
                "url": record.get("url"),
                "cadence": cadence,
                "cadence_days": interval,
                "last_successful_retrieval": record.get("last_successful_retrieval"),
                "age_days": age,
                "freshness_state": state,
            }
        )
    order = {"STALE": 0, "DUE": 1, "NEVER_OR_INVALID": 2, "FUTURE_DATE": 3, "UNKNOWN_CADENCE": 4, "CURRENT": 5}
    freshness.sort(
        key=lambda row: (
            order.get(str(row["freshness_state"]), 9),
            -(row["age_days"] if isinstance(row["age_days"], int) else -1),
            str(row.get("source_id")),
        )
    )
    return {
        "as_of": day.isoformat(),
        "source_count": len(records),
        "freshness_counts": dict(sorted(counts.items())),
        "freshness": freshness,
        "source_class_distribution": _distribution(records, "source_class"),
        "publisher_distribution": _distribution(records, "publisher"),
        "cadence_distribution": _distribution(records, "cadence"),
        "completeness": _completeness(
            records,
            (
                "source_id",
                "url",
                "publisher",
                "source_class",
                "cadence",
                "last_successful_retrieval",
                "baseline_evidence_state",
                "baseline_verification_state",
            ),
        ),
        "duplicate_source_ids": _duplicates(records, "source_id"),
        "duplicate_urls": _duplicates(records, "url", urls=True),
        "attention_states": _attention_states(
            records,
            ("baseline_evidence_state", "baseline_verification_state", "current_status"),
        ),
    }


def profile_release(release: Any, *, as_of: str | date) -> dict[str, Any]:
    if not isinstance(release, dict):
        raise ValueError("Observatory release must be a JSON object")
    day = as_of_date(as_of)
    metadata = _mapping(release.get("metadata"))
    effective_raw = metadata.get("effective_as_of", metadata.get("generated_at"))
    effective = parse_date(effective_raw)
    organizations = [item for item in _items(release.get("organizations")) if isinstance(item, dict)]
    sources = [item for item in _items(release.get("sources")) if isinstance(item, dict)]
    delta = _mapping(release.get("delta"))
    result: dict[str, Any] = {
        "as_of": day.isoformat(),
        "version": metadata.get("version"),
        "status": metadata.get("status"),
        "effective_as_of": effective_raw,
        "effective_age_days": (day - effective).days if effective else None,
        "organization_count": len(organizations),
        "source_count": len(sources),
        "delta_sections": {
            str(section): len([item for item in values if isinstance(item, dict)])
            for section, values in sorted(delta.items())
            if isinstance(values, list)
        },
        "reopening_decision_count": len(
            [item for item in _items(release.get("reopening_decisions")) if isinstance(item, dict)]
        ),
    }
    if organizations:
        result.update(
            {
                "organization_type_distribution": _distribution(organizations, "organization_type"),
                "organization_verification_distribution": _distribution(organizations, "verification_state"),
                "organization_completeness": _completeness(
                    organizations,
                    (
                        "organization_id",
                        "canonical_name",
                        "verification_state",
                        "organization_type",
                        "headquarters_country",
                        "official_url",
                    ),
                ),
                "duplicate_organization_ids": _duplicates(organizations, "organization_id"),
                "duplicate_organization_urls": _duplicates(organizations, "official_url", urls=True),
                "organization_attention_states": _attention_states(
                    organizations,
                    ("verification_state", "evidence_state", "current_status"),
                ),
            }
        )
    if sources:
        result.update(
            {
                "source_class_distribution": _distribution(sources, "source_class"),
                "source_verification_distribution": _distribution(sources, "verification_state"),
                "source_completeness": _completeness(
                    sources,
                    ("source_id", "publisher", "source_class", "url", "evidence_state", "verification_state"),
                ),
                "duplicate_source_ids": _duplicates(sources, "source_id"),
                "duplicate_source_urls": _duplicates(sources, "url", urls=True),
                "source_attention_states": _attention_states(sources, ("verification_state", "evidence_state")),
            }
        )
    effective_counts = release.get("successor_effective_counts")
    if isinstance(effective_counts, dict):
        result["successor_effective_counts"] = effective_counts
    return result


def build_data_health(*, release: Any | None = None, registry: Any | None = None, as_of: str | date) -> dict[str, Any]:
    if release is None and registry is None:
        raise ValueError("At least one release or registry is required")
    result: dict[str, Any] = {
        "metadata": {
            "title": "NeuroAI observatory data health",
            "as_of": as_of_date(as_of).isoformat(),
            "scoring": "EXPLICIT_METRICS_ONLY",
        }
    }
    if release is not None:
        result["release"] = profile_release(release, as_of=as_of)
    if registry is not None:
        result["registry"] = profile_registry(registry, as_of=as_of)
    return result


def render_data_health_markdown(health: dict[str, Any]) -> str:
    metadata = _mapping(health.get("metadata"))
    lines = ["# NeuroAI data health", "", f"As of: {metadata.get('as_of', 'UNRESOLVED')}", ""]
    release = _mapping(health.get("release"))
    if release:
        lines.extend(
            [
                "## Release",
                "",
                f"- Version: {release.get('version', 'UNRESOLVED')}",
                f"- Effective as of: {release.get('effective_as_of', 'UNRESOLVED')}",
                f"- Effective age: {release.get('effective_age_days', 'UNRESOLVED')} day(s)",
                f"- Organizations: {release.get('organization_count', 0)}",
                f"- Sources: {release.get('source_count', 0)}",
                "",
            ]
        )
    registry = _mapping(health.get("registry"))
    if registry:
        counts = _mapping(registry.get("freshness_counts"))
        lines.extend(
            [
                "## Source-monitor freshness",
                "",
                f"- Sources: {registry.get('source_count', 0)}",
                f"- Current: {counts.get('CURRENT', 0)}",
                f"- Due: {counts.get('DUE', 0)}",
                f"- Stale: {counts.get('STALE', 0)}",
                f"- Never/invalid: {counts.get('NEVER_OR_INVALID', 0)}",
                "",
                "### Highest-attention sources",
                "",
                "| Source | Publisher | Class | Cadence | Age (days) | State |",
                "| --- | --- | --- | --- | ---: | --- |",
            ]
        )
        attention = [
            item
            for item in _items(registry.get("freshness"))
            if isinstance(item, dict) and item.get("freshness_state") != "CURRENT"
        ]
        if not attention:
            lines.append("| — | — | — | — | — | All current |")
        else:
            for item in attention[:50]:
                lines.append(
                    "| {source} | {publisher} | {klass} | {cadence} | {age} | {state} |".format(
                        source=item.get("source_id"),
                        publisher=item.get("publisher"),
                        klass=item.get("source_class"),
                        cadence=item.get("cadence"),
                        age=item.get("age_days"),
                        state=item.get("freshness_state"),
                    )
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_data_health_outputs(health: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "data-health.json"
    markdown_path = output_dir / "data-health.md"
    atomic_write_json(json_path, health)
    markdown_path.write_text(render_data_health_markdown(health), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}
