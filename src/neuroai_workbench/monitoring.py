from __future__ import annotations

import ipaddress
import json
from datetime import date, datetime, timedelta, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse
from uuid import uuid4

from jsonschema import Draft202012Validator

from .events import append_event
from .util import (
    atomic_write_bytes,
    atomic_write_json,
    canonical_json_bytes,
    ensure_identifier,
    load_json,
    safe_join,
    sha256_bytes,
    sha256_file,
    utc_now,
)

OPERATIONS_RESOURCE_PACKAGE = "neuroai_workbench.resources.operations"
REGISTRY_SCHEMA = "SOURCE_MONITOR_REGISTRY.schema.json"
SNAPSHOT_SCHEMA = "MONITORING_SNAPSHOT_MANIFEST.schema.json"
CANDIDATE_SCHEMA = "CHANGE_CANDIDATE.schema.json"
ADJUDICATION_SCHEMA = "CANDIDATE_ADJUDICATION.schema.json"

CADENCE_DAYS: dict[str, int | None] = {
    "DAILY": 1,
    "WEEKLY": 7,
    "MONTHLY": 30,
    "QUARTERLY": 91,
    "ANNUAL": 365,
    "MANUAL": None,
}

ADJUDICATION_DECISIONS = frozenset({"ACCEPT", "REJECT", "DEFER", "DUPLICATE", "NEEDS_EVIDENCE"})
MATERIALITY_STATES = frozenset({"MATERIAL", "NON_MATERIAL", "UNDETERMINED"})
REOPENING_EFFECTS = frozenset(
    {
        "NO_EFFECT",
        "METADATA_UPDATE_ONLY",
        "EVIDENCE_GAP_UPDATE",
        "REVIEW_REQUIRED",
        "PARTIAL_REASSESSMENT_REQUIRED",
        "FULL_REASSESSMENT_REQUIRED",
        "UNDETERMINED",
    }
)

MAX_SNAPSHOT_BYTES = 10 * 1024 * 1024

MONITORING_BOUNDARY = (
    "Monitoring records identify retrieval and change candidates only. They do not establish scientific validity, "
    "regulatory status, clinical effectiveness, conformance, or an assessment decision without human adjudication."
)


def _public_url_error(value: str) -> str | None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "URL must use http or https and include a hostname"
    if parsed.username or parsed.password:
        return "URL must not contain embedded credentials"
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        return "URL must not target a local or internal hostname"
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return None
    if not address.is_global:
        return "URL must not target a private, loopback, link-local, reserved, multicast, or unspecified address"
    return None


def _normalize_retrieved_at(value: str | None) -> tuple[str, str]:
    raw = value or utc_now()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("retrieved_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("retrieved_at must include an explicit timezone")
    normalized = parsed.astimezone(timezone.utc)
    timestamp_id = normalized.strftime("%Y%m%dT%H%M%S%fZ")
    return normalized.isoformat().replace("+00:00", "Z"), timestamp_id


def _schema(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any], json.loads(files(OPERATIONS_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8"))
    )


def _schema_errors(value: Any, schema_name: str) -> list[dict[str, Any]]:
    validator = Draft202012Validator(_schema(schema_name))
    return [
        {
            "code": "SCHEMA_ERROR",
            "path": ".".join(str(part) for part in error.absolute_path),
            "message": error.message,
        }
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def normalize_source_registry(value: Any) -> dict[str, Any]:
    """Normalize the v1.5 legacy list into the controlled object form without changing source records."""
    if isinstance(value, list):
        return {
            "metadata": {
                "title": "NeuroAI source monitor registry",
                "version": "1.0",
                "source_release": "v1.5",
                "status": "CONTROLLED_OPERATIONAL_INPUT",
                "record_count": len(value),
                "boundary": MONITORING_BOUNDARY,
            },
            "sources": value,
        }
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    raise ValueError("Source monitor registry must be a JSON object or the legacy v1.5 JSON list")


def load_source_registry(path: Path) -> dict[str, Any]:
    return normalize_source_registry(load_json(path))


def validate_source_registry(value: Any) -> dict[str, Any]:
    registry = normalize_source_registry(value)
    errors = _schema_errors(registry, REGISTRY_SCHEMA)
    warnings: list[dict[str, Any]] = []
    sources = registry.get("sources")
    if not isinstance(sources, list):
        return {"valid": False, "errors": errors, "warnings": warnings, "counts": {}}

    monitor_ids: set[str] = set()
    source_ids: set[str] = set()
    duplicate_monitor_ids: set[str] = set()
    duplicate_source_ids: set[str] = set()
    cadence_counts: dict[str, int] = {}
    source_class_counts: dict[str, int] = {}

    for index, record in enumerate(sources):
        path = f"sources[{index}]"
        if not isinstance(record, dict):
            continue
        monitor_id = record.get("monitor_id")
        source_id = record.get("source_id")
        for field, identifier in (("monitor_id", monitor_id), ("source_id", source_id)):
            if isinstance(identifier, str):
                try:
                    ensure_identifier(identifier, field)
                except ValueError as exc:
                    errors.append({"code": "INVALID_IDENTIFIER", "path": f"{path}.{field}", "message": str(exc)})
        if isinstance(monitor_id, str):
            if monitor_id in monitor_ids:
                duplicate_monitor_ids.add(monitor_id)
            monitor_ids.add(monitor_id)
        if isinstance(source_id, str):
            if source_id in source_ids:
                duplicate_source_ids.add(source_id)
            source_ids.add(source_id)

        cadence = record.get("cadence")
        if isinstance(cadence, str):
            cadence_counts[cadence] = cadence_counts.get(cadence, 0) + 1
            if cadence not in CADENCE_DAYS:
                errors.append({"code": "UNSUPPORTED_CADENCE", "path": f"{path}.cadence", "value": cadence})

        source_class = record.get("source_class")
        if isinstance(source_class, str):
            source_class_counts[source_class] = source_class_counts.get(source_class, 0) + 1

        url = record.get("url")
        if isinstance(url, str):
            parsed = urlparse(url)
            if record.get("source_class") == "CONTROLLED_LOCAL_INPUT" and not parsed.scheme:
                warnings.append(
                    {
                        "code": "NON_PORTABLE_LOCAL_REFERENCE",
                        "path": f"{path}.url",
                        "value": url,
                        "message": "Legacy local path retained as provenance; migrate it to a content-addressed workspace object.",
                    }
                )
            else:
                url_error = _public_url_error(url)
                if url_error:
                    errors.append(
                        {
                            "code": "INVALID_PUBLIC_URL",
                            "path": f"{path}.url",
                            "value": url,
                            "message": url_error,
                        }
                    )

        last_retrieval = record.get("last_successful_retrieval")
        if isinstance(last_retrieval, str):
            try:
                date.fromisoformat(last_retrieval)
            except ValueError:
                errors.append(
                    {
                        "code": "INVALID_RETRIEVAL_DATE",
                        "path": f"{path}.last_successful_retrieval",
                        "value": last_retrieval,
                    }
                )

    if duplicate_monitor_ids:
        errors.append({"code": "DUPLICATE_MONITOR_ID", "path": "sources", "identifiers": sorted(duplicate_monitor_ids)})
    if duplicate_source_ids:
        errors.append({"code": "DUPLICATE_SOURCE_ID", "path": "sources", "identifiers": sorted(duplicate_source_ids)})

    # Non-fatal: multiple logical sources may share one retrieval target URL.
    from .collector.url_normalize import normalize_retrieval_url

    url_groups: dict[str, list[str]] = {}
    for record in sources:
        if not isinstance(record, dict):
            continue
        url = record.get("url")
        source_id = record.get("source_id")
        if not isinstance(url, str) or not isinstance(source_id, str):
            continue
        if record.get("source_class") == "CONTROLLED_LOCAL_INPUT" and not urlparse(url).scheme:
            continue
        normalized = normalize_retrieval_url(url)
        if not normalized.startswith(("http://", "https://")):
            continue
        url_groups.setdefault(normalized, []).append(source_id)
    for normalized_url, identifiers in sorted(url_groups.items()):
        unique_ids = sorted(set(identifiers))
        if len(unique_ids) > 1:
            warnings.append(
                {
                    "code": "DUPLICATE_RETRIEVAL_URL",
                    "path": "sources",
                    "normalized_url": normalized_url,
                    "identifiers": unique_ids,
                    "message": (
                        "Multiple source_id values share one retrieval target; "
                        "scheduler should fetch once and fan out linkages."
                    ),
                }
            )

    declared_count = registry.get("metadata", {}).get("record_count")
    if isinstance(declared_count, int) and declared_count != len(sources):
        errors.append(
            {
                "code": "RECORD_COUNT_MISMATCH",
                "path": "metadata.record_count",
                "declared": declared_count,
                "observed": len(sources),
            }
        )

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "sources": len(sources),
            "cadences": cadence_counts,
            "source_classes": source_class_counts,
        },
        "boundary": MONITORING_BOUNDARY,
    }


def _monitoring_root(workspace: Path) -> Path:
    return workspace / "observatory" / "monitoring"


def _registry_path(workspace: Path) -> Path:
    return _monitoring_root(workspace) / "registry" / "registry.json"


def _state_path(workspace: Path) -> Path:
    return _monitoring_root(workspace) / "state.json"


def _events_path(workspace: Path) -> Path:
    return _monitoring_root(workspace) / "events.jsonl"


def initialize_monitoring(workspace: Path, registry_path: Path, actor: str = "local-user") -> dict[str, Any]:
    registry = load_source_registry(registry_path)
    validation = validate_source_registry(registry)
    if not validation["valid"]:
        raise ValueError(f"Source registry is invalid: {json.dumps(validation, ensure_ascii=False)}")

    target = _registry_path(workspace)
    registry_hash = sha256_bytes(canonical_json_bytes(registry))
    if target.exists():
        existing = cast(dict[str, Any], load_json(target))
        existing_hash = sha256_bytes(canonical_json_bytes(existing))
        if existing_hash != registry_hash:
            raise ValueError("Monitoring registry already exists with different canonical content")
    else:
        atomic_write_json(target, registry)

    state_path = _state_path(workspace)
    if not state_path.exists():
        atomic_write_json(
            state_path,
            {
                "version": "1",
                "registry_sha256": registry_hash,
                "sources": {},
                "boundary": MONITORING_BOUNDARY,
            },
        )

    root = _monitoring_root(workspace)
    for relative in ("snapshots", "candidates", "adjudications", "runs"):
        (root / relative).mkdir(parents=True, exist_ok=True)

    append_event(
        _events_path(workspace),
        "MONITORING_INITIALIZED",
        actor,
        {"registry_sha256": registry_hash, "source_count": validation["counts"]["sources"]},
    )
    return {
        "monitoring_root": str(root),
        "registry_sha256": registry_hash,
        "source_count": validation["counts"]["sources"],
        "validation": validation,
        "boundary": MONITORING_BOUNDARY,
    }


def _load_registry_and_state(workspace: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    registry_path = _registry_path(workspace)
    state_path = _state_path(workspace)
    if not registry_path.is_file() or not state_path.is_file():
        raise ValueError("Monitoring is not initialized for this workspace")
    registry = cast(dict[str, Any], load_json(registry_path))
    state = cast(dict[str, Any], load_json(state_path))
    observed_hash = sha256_bytes(canonical_json_bytes(registry))
    if state.get("registry_sha256") != observed_hash:
        raise ValueError("Monitoring registry hash does not match state; explicit migration is required")
    return registry, state


def _parse_day(value: str | date | None) -> date:
    if value is None:
        return datetime.now(timezone.utc).date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def plan_monitoring_run(
    workspace: Path,
    as_of: str | date | None = None,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    registry, state = _load_registry_and_state(workspace)
    as_of_day = _parse_day(as_of)
    selected = set(source_ids or [])
    known_ids = {record.get("source_id") for record in registry["sources"] if isinstance(record, dict)}
    unknown = sorted(selected - known_ids)
    if unknown:
        raise ValueError(f"Unknown source IDs: {', '.join(unknown)}")

    due: list[dict[str, Any]] = []
    manual: list[dict[str, Any]] = []
    not_due: list[dict[str, Any]] = []
    source_state = state.get("sources", {})
    if not isinstance(source_state, dict):
        raise ValueError("Monitoring state sources must be an object")

    for record in registry["sources"]:
        if not isinstance(record, dict):
            continue
        source_id = str(record["source_id"])
        if selected and source_id not in selected:
            continue
        cadence = str(record["cadence"])
        cadence_days = CADENCE_DAYS[cadence]
        state_record = source_state.get(source_id, {})
        last_checked = state_record.get("last_checked") if isinstance(state_record, dict) else None
        baseline_checked = record.get("last_successful_retrieval")
        checked_value = last_checked or baseline_checked
        checked_day = date.fromisoformat(checked_value) if isinstance(checked_value, str) else None
        item = {
            "monitor_id": record["monitor_id"],
            "source_id": source_id,
            "url": record["url"],
            "publisher": record["publisher"],
            "source_class": record["source_class"],
            "cadence": cadence,
            "last_checked": checked_day.isoformat() if checked_day else None,
            "next_action": record["next_action"],
            "network_access_required": bool(record.get("network_access_required", True)),
        }
        # Local / no-network sources never enter the HTTP collector due queue.
        if record.get("source_class") == "CONTROLLED_LOCAL_INPUT" or record.get("network_access_required") is False:
            item["manual_reason"] = "CONTROLLED_LOCAL_OR_NO_NETWORK"
            manual.append(item)
            continue
        if cadence_days is None:
            item["manual_reason"] = "CADENCE_MANUAL"
            manual.append(item)
            continue
        due_on = checked_day + timedelta(days=cadence_days) if checked_day else as_of_day
        item["due_on"] = due_on.isoformat()
        item["overdue_days"] = max(0, (as_of_day - due_on).days)
        if due_on <= as_of_day:
            due.append(item)
        else:
            not_due.append(item)

    priority = {"DAILY": 0, "WEEKLY": 1, "MONTHLY": 2, "QUARTERLY": 3, "ANNUAL": 4}
    due.sort(key=lambda item: (-int(item["overdue_days"]), priority.get(str(item["cadence"]), 99), item["source_id"]))
    plan_payload = {
        "as_of": as_of_day.isoformat(),
        "due": due,
        "manual": manual,
        "not_due": not_due,
    }
    plan_id = f"PLAN-{as_of_day.isoformat()}-{sha256_bytes(canonical_json_bytes(plan_payload))[:12]}"
    return {
        "plan_id": plan_id,
        **plan_payload,
        "counts": {"due": len(due), "manual": len(manual), "not_due": len(not_due)},
        "boundary": MONITORING_BOUNDARY,
    }


def _registry_record(registry: dict[str, Any], source_id: str) -> dict[str, Any]:
    ensure_identifier(source_id, "source ID")
    for record in registry["sources"]:
        if isinstance(record, dict) and record.get("source_id") == source_id:
            return cast(dict[str, Any], record)
    raise ValueError(f"Unknown source ID {source_id!r}")


def _text_digest(data: bytes, media_type: str) -> str | None:
    textual = media_type.startswith("text/") or any(
        token in media_type for token in ("json", "xml", "javascript", "html", "csv")
    )
    if not textual:
        return None
    text = data.decode("utf-8", errors="replace")
    normalized = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")).strip()
    return sha256_bytes(normalized.encode("utf-8"))


def record_snapshot(
    workspace: Path,
    source_id: str,
    data: bytes,
    *,
    media_type: str = "application/octet-stream",
    retrieved_at: str | None = None,
    retrieval_url: str | None = None,
    original_filename: str | None = None,
    actor: str = "local-user",
) -> dict[str, Any]:
    if not data:
        raise ValueError("A successful snapshot cannot contain zero bytes")
    if len(data) > MAX_SNAPSHOT_BYTES:
        raise ValueError(f"Snapshot exceeds the {MAX_SNAPSHOT_BYTES}-byte local ingestion limit")
    registry, state = _load_registry_and_state(workspace)
    source = _registry_record(registry, source_id)
    retrieved, timestamp_id = _normalize_retrieved_at(retrieved_at)
    retrieval_reference = retrieval_url or str(source["url"])
    if source.get("source_class") != "CONTROLLED_LOCAL_INPUT":
        url_error = _public_url_error(retrieval_reference)
        if url_error:
            raise ValueError(f"retrieval_url is invalid: {url_error}")
    if original_filename is not None and Path(original_filename).name != original_filename:
        raise ValueError("original_filename must be a basename without directory components")

    digest = sha256_bytes(data)
    snapshot_id = f"SNAP-{source_id}-{timestamp_id}-{digest[:12]}"
    snapshot_root = safe_join(_monitoring_root(workspace) / "snapshots", source_id)
    content_path = safe_join(snapshot_root, f"{digest}.bin")
    manifest_path = safe_join(snapshot_root, f"{snapshot_id}.json")
    atomic_write_bytes(content_path, data)
    manifest = {
        "snapshot_id": snapshot_id,
        "source_id": source_id,
        "monitor_id": source["monitor_id"],
        "retrieved_at": retrieved,
        "retrieval_url": retrieval_reference,
        "media_type": media_type,
        "size_bytes": len(data),
        "sha256": digest,
        "normalized_text_sha256": _text_digest(data, media_type),
        "stored_path": str(content_path.relative_to(workspace)),
        "original_filename": original_filename,
        "evidence_state": "RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED",
        "boundary": MONITORING_BOUNDARY,
    }
    errors = _schema_errors(manifest, SNAPSHOT_SCHEMA)
    if errors:
        raise ValueError(f"Snapshot manifest failed validation: {json.dumps(errors, ensure_ascii=False)}")
    if manifest_path.exists():
        existing = cast(dict[str, Any], load_json(manifest_path))
        if canonical_json_bytes(existing) != canonical_json_bytes(manifest):
            raise ValueError("Refusing to overwrite an existing snapshot manifest with different metadata")
    else:
        atomic_write_json(manifest_path, manifest)

    source_state = state.setdefault("sources", {})
    if not isinstance(source_state, dict):
        raise ValueError("Monitoring state sources must be an object")
    previous = source_state.get(source_id, {})
    previous_id = previous.get("last_snapshot_id") if isinstance(previous, dict) else None
    source_state[source_id] = {
        "last_checked": retrieved[:10],
        "last_snapshot_id": snapshot_id,
        "previous_snapshot_id": previous_id,
        "last_snapshot_sha256": digest,
    }
    atomic_write_json(_state_path(workspace), state)
    append_event(
        _events_path(workspace),
        "SOURCE_SNAPSHOT_RECORDED",
        actor,
        {
            "source_id": source_id,
            "snapshot_id": snapshot_id,
            "sha256": digest,
            "previous_snapshot_id": previous_id,
        },
    )
    return manifest


def record_snapshot_file(
    workspace: Path,
    source_id: str,
    source_file: Path,
    *,
    media_type: str = "application/octet-stream",
    retrieved_at: str | None = None,
    actor: str = "local-user",
) -> dict[str, Any]:
    if not source_file.is_file():
        raise ValueError(f"Snapshot input file does not exist: {source_file}")
    return record_snapshot(
        workspace,
        source_id,
        source_file.read_bytes(),
        media_type=media_type,
        retrieved_at=retrieved_at,
        original_filename=source_file.name,
        actor=actor,
    )


def load_snapshot(workspace: Path, source_id: str, snapshot_id: str) -> dict[str, Any]:
    ensure_identifier(source_id, "source ID")
    ensure_identifier(snapshot_id, "snapshot ID")
    path = safe_join(_monitoring_root(workspace) / "snapshots", source_id, f"{snapshot_id}.json")
    if not path.is_file():
        raise ValueError(f"Unknown snapshot {snapshot_id!r} for source {source_id!r}")
    value = cast(dict[str, Any], load_json(path))
    errors = _schema_errors(value, SNAPSHOT_SCHEMA)
    if errors:
        raise ValueError(f"Stored snapshot manifest is invalid: {json.dumps(errors, ensure_ascii=False)}")
    content_path = safe_join(workspace, str(value["stored_path"]))
    if not content_path.is_file() or sha256_file(content_path) != value["sha256"]:
        raise ValueError("Stored snapshot bytes do not match the manifest")
    return value


def compare_snapshots(
    workspace: Path, source_id: str, older_snapshot_id: str, newer_snapshot_id: str
) -> dict[str, Any]:
    older = load_snapshot(workspace, source_id, older_snapshot_id)
    newer = load_snapshot(workspace, source_id, newer_snapshot_id)
    if older["sha256"] == newer["sha256"]:
        classification = "NO_CHANGE"
    elif older.get("normalized_text_sha256") and older.get("normalized_text_sha256") == newer.get(
        "normalized_text_sha256"
    ):
        classification = "NON_MATERIAL_REPRESENTATION_CHANGE"
    else:
        classification = "CONTENT_CHANGED_REQUIRES_REVIEW"
    result = {
        "comparison_id": f"CMP-{source_id}-{older['sha256'][:8]}-{newer['sha256'][:8]}",
        "source_id": source_id,
        "older_snapshot_id": older_snapshot_id,
        "newer_snapshot_id": newer_snapshot_id,
        "older_sha256": older["sha256"],
        "newer_sha256": newer["sha256"],
        "classification": classification,
        "size_delta_bytes": int(newer["size_bytes"]) - int(older["size_bytes"]),
        "candidate_required": classification == "CONTENT_CHANGED_REQUIRES_REVIEW",
        "boundary": MONITORING_BOUNDARY,
    }
    return result


def create_change_candidate(
    workspace: Path,
    source_id: str,
    current_snapshot_id: str,
    *,
    previous_snapshot_id: str | None = None,
    summary: str = "Automated content change detected; substantive classification pending human review.",
    actor: str = "local-user",
) -> dict[str, Any]:
    current = load_snapshot(workspace, source_id, current_snapshot_id)
    comparison = None
    if previous_snapshot_id:
        comparison = compare_snapshots(workspace, source_id, previous_snapshot_id, current_snapshot_id)
        if not comparison["candidate_required"]:
            raise ValueError("A change candidate is not required for this snapshot comparison")
    candidate_id = f"CAND-{uuid4().hex}"
    candidate = {
        "candidate_id": candidate_id,
        "created_at": utc_now(),
        "created_by": actor,
        "source_id": source_id,
        "source_snapshot_ids": [item for item in (previous_snapshot_id, current_snapshot_id) if item],
        "current_snapshot_sha256": current["sha256"],
        "detection": comparison or {"classification": "MANUAL_CANDIDATE"},
        "summary": summary,
        "proposed_change_class": "UNCLASSIFIED",
        "proposed_materiality": "UNDETERMINED",
        "proposed_reopening_effect": "UNDETERMINED",
        "extracted_claims": [],
        "status": "PENDING_HUMAN_ADJUDICATION",
        "automatic_mutation_performed": False,
        "boundary": MONITORING_BOUNDARY,
    }
    errors = _schema_errors(candidate, CANDIDATE_SCHEMA)
    if errors:
        raise ValueError(f"Change candidate failed validation: {json.dumps(errors, ensure_ascii=False)}")
    path = safe_join(_monitoring_root(workspace) / "candidates", f"{candidate_id}.json")
    atomic_write_json(path, candidate)
    append_event(
        _events_path(workspace),
        "CHANGE_CANDIDATE_CREATED",
        actor,
        {"candidate_id": candidate_id, "source_id": source_id, "snapshot_sha256": current["sha256"]},
    )
    return candidate


def load_change_candidate(workspace: Path, candidate_id: str) -> dict[str, Any]:
    ensure_identifier(candidate_id, "candidate ID")
    path = safe_join(_monitoring_root(workspace) / "candidates", f"{candidate_id}.json")
    if not path.is_file():
        raise ValueError(f"Unknown change candidate {candidate_id!r}")
    value = cast(dict[str, Any], load_json(path))
    errors = _schema_errors(value, CANDIDATE_SCHEMA)
    if errors:
        raise ValueError(f"Stored change candidate is invalid: {json.dumps(errors, ensure_ascii=False)}")
    return value


def adjudicate_change_candidate(
    workspace: Path,
    candidate_id: str,
    decision: str,
    *,
    rationale: str,
    change_class: str = "UNCLASSIFIED",
    materiality: str = "UNDETERMINED",
    reopening_effect: str = "UNDETERMINED",
    actor: str = "local-user",
) -> dict[str, Any]:
    candidate = load_change_candidate(workspace, candidate_id)
    if decision not in ADJUDICATION_DECISIONS:
        raise ValueError(f"Unsupported adjudication decision {decision!r}")
    if materiality not in MATERIALITY_STATES:
        raise ValueError(f"Unsupported materiality state {materiality!r}")
    if reopening_effect not in REOPENING_EFFECTS:
        raise ValueError(f"Unsupported reopening effect {reopening_effect!r}")
    if not rationale.strip():
        raise ValueError("Adjudication rationale is required")
    if decision == "ACCEPT" and (
        change_class == "UNCLASSIFIED" or materiality == "UNDETERMINED" or reopening_effect == "UNDETERMINED"
    ):
        raise ValueError("Accepted candidates require explicit change class, materiality, and reopening effect")

    adjudication_id = f"ADJ-{candidate_id.removeprefix('CAND-')}"
    adjudication = {
        "adjudication_id": adjudication_id,
        "candidate_id": candidate_id,
        "candidate_sha256": sha256_bytes(canonical_json_bytes(candidate)),
        "decided_at": utc_now(),
        "decided_by": actor,
        "decision": decision,
        "change_class": change_class,
        "materiality": materiality,
        "reopening_effect": reopening_effect,
        "rationale": rationale,
        "canonical_observatory_mutation_performed": False,
        "boundary": MONITORING_BOUNDARY,
    }
    errors = _schema_errors(adjudication, ADJUDICATION_SCHEMA)
    if errors:
        raise ValueError(f"Candidate adjudication failed validation: {json.dumps(errors, ensure_ascii=False)}")
    path = safe_join(_monitoring_root(workspace) / "adjudications", f"{adjudication_id}.json")
    if path.exists():
        raise ValueError("A candidate adjudication is immutable and already exists")
    atomic_write_json(path, adjudication)
    append_event(
        _events_path(workspace),
        "CHANGE_CANDIDATE_ADJUDICATED",
        actor,
        {
            "candidate_id": candidate_id,
            "adjudication_id": adjudication_id,
            "decision": decision,
            "reopening_effect": reopening_effect,
        },
    )
    return adjudication


def _load_records(directory: Path) -> list[dict[str, Any]]:
    if not directory.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        value = load_json(path)
        if isinstance(value, dict):
            records.append(cast(dict[str, Any], value))
    return records


def build_refresh_candidate(
    workspace: Path,
    version: str,
    evidence_cutoff: str,
    actor: str = "local-user",
) -> dict[str, Any]:
    ensure_identifier(version, "refresh candidate version")
    date.fromisoformat(evidence_cutoff)
    registry, _ = _load_registry_and_state(workspace)
    candidates = _load_records(_monitoring_root(workspace) / "candidates")
    adjudications = _load_records(_monitoring_root(workspace) / "adjudications")
    adjudication_by_candidate = {record.get("candidate_id"): record for record in adjudications}
    accepted = [
        {"candidate": candidate, "adjudication": adjudication_by_candidate[candidate["candidate_id"]]}
        for candidate in candidates
        if adjudication_by_candidate.get(candidate["candidate_id"], {}).get("decision") == "ACCEPT"
    ]
    unresolved = [candidate for candidate in candidates if candidate["candidate_id"] not in adjudication_by_candidate]
    reopening_queue = [
        {
            "candidate_id": item["candidate"]["candidate_id"],
            "source_id": item["candidate"]["source_id"],
            "reopening_effect": item["adjudication"]["reopening_effect"],
            "rationale": item["adjudication"]["rationale"],
        }
        for item in accepted
        if item["adjudication"]["reopening_effect"] not in {"NO_EFFECT", "UNDETERMINED"}
    ]
    package = {
        "metadata": {
            "title": "NeuroAI observatory refresh candidate",
            "version": version,
            "evidence_cutoff": evidence_cutoff,
            "generated_at": utc_now(),
            "generated_by": actor,
            "status": "REVIEW_CANDIDATE_NOT_CANONICAL",
        },
        "registry_reference": {
            "sha256": sha256_bytes(canonical_json_bytes(registry)),
            "source_count": len(registry["sources"]),
        },
        "change_candidates": candidates,
        "adjudications": adjudications,
        "accepted_changes": accepted,
        "unresolved_candidates": unresolved,
        "reopening_queue": reopening_queue,
        "counts": {
            "candidates": len(candidates),
            "adjudications": len(adjudications),
            "accepted": len(accepted),
            "unresolved": len(unresolved),
            "reopening_queue": len(reopening_queue),
        },
        "withheld_claims": [
            "This package is not a canonical observatory successor release.",
            "Accepted monitoring candidates do not establish substantive truth without domain review.",
            "No assessment is reopened or modified automatically.",
            "No UNESCO endorsement, regulatory decision, clinical conclusion, or conformance determination is created.",
        ],
        "boundary": MONITORING_BOUNDARY,
    }
    run_root = safe_join(_monitoring_root(workspace) / "runs", version)
    package_path = safe_join(run_root, "refresh-candidate.json")
    if package_path.exists():
        raise ValueError("Refusing to overwrite an existing refresh candidate package")
    atomic_write_json(package_path, package)
    manifest = {
        "version": version,
        "refresh_candidate_sha256": sha256_file(package_path),
        "path": str(package_path.relative_to(workspace)),
        "status": "REVIEW_CANDIDATE_NOT_CANONICAL",
        "boundary": MONITORING_BOUNDARY,
    }
    atomic_write_json(safe_join(run_root, "manifest.json"), manifest)
    append_event(
        _events_path(workspace),
        "REFRESH_CANDIDATE_BUILT",
        actor,
        {"version": version, "sha256": manifest["refresh_candidate_sha256"], "counts": package["counts"]},
    )
    return {"package": package, "manifest": manifest}


def monitoring_status(workspace: Path) -> dict[str, Any]:
    registry, state = _load_registry_and_state(workspace)
    candidates = _load_records(_monitoring_root(workspace) / "candidates")
    adjudications = _load_records(_monitoring_root(workspace) / "adjudications")
    runs = sorted(path.name for path in (_monitoring_root(workspace) / "runs").glob("*") if path.is_dir())
    adjudicated_ids = {record.get("candidate_id") for record in adjudications}
    return {
        "registry_sha256": state["registry_sha256"],
        "source_count": len(registry["sources"]),
        "sources_checked": len(state.get("sources", {})),
        "candidate_count": len(candidates),
        "adjudication_count": len(adjudications),
        "pending_candidate_count": sum(1 for item in candidates if item.get("candidate_id") not in adjudicated_ids),
        "run_versions": runs,
        "boundary": MONITORING_BOUNDARY,
    }


def build_source_health_report(
    workspace: Path,
    *,
    as_of: str | date | None = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Structured source-health report from registry, state, and due-source plan.

    Records operational retrieval posture only. Does not establish substantive validity.
    """
    registry, state = _load_registry_and_state(workspace)
    as_of_day = _parse_day(as_of)
    effective_plan = plan or plan_monitoring_run(workspace, as_of=as_of_day)
    due_ids = {item["source_id"] for item in effective_plan.get("due", [])}
    manual_ids = {item["source_id"] for item in effective_plan.get("manual", [])}
    not_due_ids = {item["source_id"] for item in effective_plan.get("not_due", [])}
    overdue_by_id = {
        item["source_id"]: int(item.get("overdue_days") or 0)
        for item in effective_plan.get("due", [])
        if isinstance(item, dict)
    }

    source_state = state.get("sources", {})
    if not isinstance(source_state, dict):
        raise ValueError("Monitoring state sources must be an object")

    rows: list[dict[str, Any]] = []
    class_counts: dict[str, int] = {}
    failure_class_counts: dict[str, int] = {}
    obsolete_count = 0
    controlled_local_count = 0

    for record in registry["sources"]:
        if not isinstance(record, dict):
            continue
        source_id = str(record["source_id"])
        monitor_id = str(record["monitor_id"])
        source_class = str(record.get("source_class", "UNKNOWN"))
        class_counts[source_class] = class_counts.get(source_class, 0) + 1
        state_record = source_state.get(source_id, {})
        if not isinstance(state_record, dict):
            state_record = {}
        last_retrieval = state_record.get("last_checked") or record.get("last_successful_retrieval")
        failure_class = state_record.get("last_failure_class") or record.get("last_failure_class") or "NONE"
        if not isinstance(failure_class, str):
            failure_class = "NONE"
        failure_class_counts[failure_class] = failure_class_counts.get(failure_class, 0) + 1
        raw_flags = record.get("status_flags")
        status_flags: list[Any] = raw_flags if isinstance(raw_flags, list) else []
        obsolete = bool(
            record.get("obsolete")
            or record.get("withdrawn")
            or any(isinstance(flag, str) and flag in {"OBSOLETE", "WITHDRAWN"} for flag in status_flags)
        )
        if obsolete:
            obsolete_count += 1
        controlled_local = source_class == "CONTROLLED_LOCAL_INPUT"
        if controlled_local:
            controlled_local_count += 1
        if source_id in due_ids:
            schedule_state = "OVERDUE" if overdue_by_id.get(source_id, 0) > 0 else "DUE"
        elif source_id in manual_ids:
            schedule_state = "MANUAL"
        elif source_id in not_due_ids:
            schedule_state = "NOT_DUE"
        else:
            schedule_state = "UNPLANNED"
        rows.append(
            {
                "monitor_id": monitor_id,
                "source_id": source_id,
                "source_class": source_class,
                "schedule_state": schedule_state,
                "overdue_days": overdue_by_id.get(source_id, 0),
                "last_retrieval": last_retrieval,
                "failure_class": failure_class,
                "obsolete_or_withdrawn": obsolete,
                "controlled_local_warning": controlled_local,
            }
        )

    rows.sort(key=lambda item: (item["schedule_state"], -int(item["overdue_days"]), item["source_id"]))
    planned_ids = due_ids | manual_ids | not_due_ids
    registry_ids = {str(item["source_id"]) for item in registry["sources"] if isinstance(item, dict)}
    silent_drop = sorted(registry_ids - planned_ids)
    report = {
        "schema_version": "1.0",
        "as_of": as_of_day.isoformat(),
        "registry_sha256": state["registry_sha256"],
        "plan_id": effective_plan.get("plan_id"),
        "counts": {
            "sources": len(rows),
            "due": len(due_ids),
            "manual": len(manual_ids),
            "not_due": len(not_due_ids),
            "overdue": sum(1 for item in rows if item["schedule_state"] == "OVERDUE"),
            "obsolete_or_withdrawn": obsolete_count,
            "controlled_local": controlled_local_count,
            "silent_drop": len(silent_drop),
        },
        "source_class_counts": dict(sorted(class_counts.items())),
        "failure_class_counts": dict(sorted(failure_class_counts.items())),
        "silent_drop_source_ids": silent_drop,
        "sources": rows,
        "boundary": MONITORING_BOUNDARY,
    }
    return report
