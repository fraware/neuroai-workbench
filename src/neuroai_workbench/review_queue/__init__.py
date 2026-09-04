"""Append-only observatory monitoring review queue over monitoring projections."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from jsonschema import Draft202012Validator

from ..events import append_event, verify_chain
from ..monitoring import monitoring_status
from ..util import (
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
QUEUE_ITEM_SCHEMA = "REVIEW_QUEUE_ITEM.schema.json"
LEASE_SCHEMA = "REVIEW_LEASE.schema.json"
LEASE_RELEASE_SCHEMA = "REVIEW_LEASE_RELEASE.schema.json"
OPINION_SCHEMA = "REVIEW_OPINION.schema.json"
PROFILE_SCHEMA = "REVIEW_PROFILE.schema.json"

PROJECTION_VERSION = "1"
DEFAULT_LEASE_TTL_SECONDS = 3600
MAX_LEASE_TTL_SECONDS = 86400

QUEUE_ROLES = frozenset(
    {
        "MONITORING_REVIEWER",
        "ADJUDICATION_REVIEWER",
        "LEAD_MONITORING_REVIEWER",
        "OBSERVER",
    }
)
OPINION_POSITIONS = frozenset({"SUPPORT", "OPPOSE", "DEFER", "ABSTAIN", "NEEDS_EVIDENCE"})
RELEASE_REASONS = frozenset({"RELEASED", "EXPIRED", "SUPERSEDED"})

REVIEW_QUEUE_BOUNDARY = (
    "The review queue projects monitoring candidates and adjudications for local workflow attribution. "
    "It does not authenticate reviewers, mutate canonical observatory or assessment records, "
    "or establish substantive scientific, regulatory, clinical, or conformance conclusions."
)
IDENTITY_BOUNDARY = (
    "The workbench records a claimed local profile identifier and role; "
    "it does not authenticate a person or institution."
)

MONITORING_ROOT_REL = Path("observatory") / "monitoring"
QUEUE_ROOT_REL = Path("observatory") / "review_queue"


def _schema(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(OPERATIONS_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
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


def _hash_record(value: dict[str, Any], hash_field: str) -> str:
    controlled = {key: item for key, item in value.items() if key != hash_field and not key.startswith("_")}
    return sha256_bytes(canonical_json_bytes(controlled))


def _queue_root(workspace: Path) -> Path:
    return workspace / QUEUE_ROOT_REL


def _events_path(workspace: Path) -> Path:
    return _queue_root(workspace) / "events.jsonl"


def _monitoring_root(workspace: Path) -> Path:
    return workspace / MONITORING_ROOT_REL


def _require_monitoring(workspace: Path) -> None:
    registry = _monitoring_root(workspace) / "registry" / "registry.json"
    state = _monitoring_root(workspace) / "state.json"
    if not registry.is_file() or not state.is_file():
        raise ValueError("Monitoring must be initialized before using the review queue")


def _load_records(directory: Path) -> list[dict[str, Any]]:
    if not directory.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        value = load_json(path)
        if isinstance(value, dict):
            item = cast(dict[str, Any], value)
            item["_path"] = str(path)
            records.append(item)
    return records


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include an explicit timezone")
    return parsed.astimezone(timezone.utc)


def _item_id_for_candidate(candidate_id: str) -> str:
    ensure_identifier(candidate_id, "candidate ID")
    if not candidate_id.startswith("CAND-"):
        raise ValueError(f"Unsupported candidate ID format: {candidate_id!r}")
    return f"RQI-{candidate_id}"


def _candidate_id_from_item(item_id: str) -> str:
    ensure_identifier(item_id, "queue item ID")
    if not item_id.startswith("RQI-CAND-"):
        raise ValueError(f"Unsupported queue item ID: {item_id!r}")
    return item_id.removeprefix("RQI-")


def initialize_review_queue(workspace: Path, actor: str = "local-user") -> dict[str, Any]:
    ensure_identifier(actor, "actor ID")
    _require_monitoring(workspace)
    root = _queue_root(workspace)
    for relative in ("profiles", "leases", "lease_releases", "opinions", "projections"):
        (root / relative).mkdir(parents=True, exist_ok=True)
    events_path = _events_path(workspace)
    if not events_path.exists():
        events_path.write_text("", encoding="utf-8")
    append_event(
        events_path,
        "REVIEW_QUEUE_INITIALIZED",
        actor,
        {"projection_version": PROJECTION_VERSION},
    )
    return {
        "review_queue_root": str(root),
        "projection_version": PROJECTION_VERSION,
        "boundary": REVIEW_QUEUE_BOUNDARY,
    }


def register_reviewer_profile(
    workspace: Path,
    profile_id: str,
    display_name: str,
    roles: list[str],
    *,
    actor: str = "local-user",
) -> dict[str, Any]:
    ensure_identifier(profile_id, "profile ID")
    ensure_identifier(actor, "actor ID")
    display_name = display_name.strip()
    if not display_name:
        raise ValueError("display_name must not be empty")
    selected_roles = sorted(set(roles))
    if not selected_roles:
        raise ValueError("At least one review queue role is required")
    unknown_roles = sorted(set(selected_roles) - QUEUE_ROLES)
    if unknown_roles:
        raise ValueError(f"Unsupported review queue roles: {', '.join(unknown_roles)}")

    root = _queue_root(workspace)
    if not root.is_dir():
        raise ValueError("Review queue is not initialized for this workspace")
    output = safe_join(root / "profiles", f"{profile_id}.json")
    requested_identity = {
        "profile_id": profile_id,
        "display_name": display_name,
        "roles": selected_roles,
        "registered_by": actor,
        "authority_profile": "LOCAL_UNAUTHENTICATED_ATTRIBUTION",
        "identity_boundary": IDENTITY_BOUNDARY,
        "boundary": REVIEW_QUEUE_BOUNDARY,
    }
    if output.exists():
        existing = _load_profile(workspace, profile_id)
        existing_identity = {key: existing.get(key) for key in requested_identity}
        if canonical_json_bytes(existing_identity) != canonical_json_bytes(requested_identity):
            raise ValueError(f"Review profile {profile_id!r} already exists with different content")
        return {"profile": existing, "path": str(output), "created": False}

    record = {**requested_identity, "registered_at": utc_now()}
    record["profile_sha256"] = _hash_record(record, "profile_sha256")
    errors = _schema_errors(record, PROFILE_SCHEMA)
    if errors:
        raise ValueError(f"Review profile failed validation: {json.dumps(errors, ensure_ascii=False)}")
    atomic_write_json(output, record)
    append_event(
        _events_path(workspace),
        "REVIEW_PROFILE_REGISTERED",
        actor,
        {"profile_id": profile_id, "roles": selected_roles, "profile_sha256": record["profile_sha256"]},
    )
    return {"profile": record, "path": str(output), "created": True}


def load_reviewer_profiles(workspace: Path) -> list[dict[str, Any]]:
    return _load_records(_queue_root(workspace) / "profiles")


def _load_profile(workspace: Path, profile_id: str) -> dict[str, Any]:
    path = safe_join(_queue_root(workspace) / "profiles", f"{profile_id}.json")
    if not path.is_file():
        raise ValueError(f"Unknown reviewer profile {profile_id!r}")
    profile = cast(dict[str, Any], load_json(path))
    if profile.get("profile_sha256") != _hash_record(profile, "profile_sha256"):
        raise ValueError(f"Review profile {profile_id!r} has an invalid hash")
    errors = _schema_errors(profile, PROFILE_SCHEMA)
    if errors:
        raise ValueError(f"Stored review profile is invalid: {json.dumps(errors, ensure_ascii=False)}")
    return profile


def _load_monitoring_candidates(workspace: Path) -> list[dict[str, Any]]:
    return _load_records(_monitoring_root(workspace) / "candidates")


def _build_queue_item(
    candidate: dict[str, Any],
    adjudication: dict[str, Any] | None,
    *,
    stale_reason: str | None = None,
) -> dict[str, Any]:
    candidate_id = str(candidate["candidate_id"])
    item: dict[str, Any] = {
        "item_id": _item_id_for_candidate(candidate_id),
        "item_type": "CHANGE_CANDIDATE",
        "source_id": str(candidate["source_id"]),
        "candidate_id": candidate_id,
        "monitoring_record_sha256": sha256_bytes(canonical_json_bytes(candidate)),
        "queue_status": "OPEN",
        "snapshot_ids": list(candidate.get("source_snapshot_ids", [])),
        "projection_version": PROJECTION_VERSION,
        "boundary": REVIEW_QUEUE_BOUNDARY,
    }
    if adjudication is not None and stale_reason is None:
        item["queue_status"] = "ADJUDICATED"
        item["adjudication_id"] = adjudication["adjudication_id"]
        item["adjudication_decision"] = adjudication["decision"]
    if stale_reason:
        item["queue_status"] = "STALE"
        item["stale_reason"] = stale_reason
    errors = _schema_errors(item, QUEUE_ITEM_SCHEMA)
    if errors:
        raise ValueError(f"Queue item projection failed validation: {json.dumps(errors, ensure_ascii=False)}")
    return item


def rebuild_queue_projection(workspace: Path) -> list[dict[str, Any]]:
    _require_monitoring(workspace)
    candidates = _load_monitoring_candidates(workspace)
    adjudications = _load_records(_monitoring_root(workspace) / "adjudications")
    adjudication_by_candidate = {str(item["candidate_id"]): item for item in adjudications}
    opinions_by_item = _opinions_by_item(workspace)
    items: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = str(candidate["candidate_id"])
        item_id = _item_id_for_candidate(candidate_id)
        current_hash = sha256_bytes(canonical_json_bytes(candidate))
        stale_opinions = [
            opinion
            for opinion in opinions_by_item.get(item_id, [])
            if opinion.get("monitoring_record_sha256") != current_hash
        ]
        stale_reason = None
        if stale_opinions:
            stale_reason = "Monitoring candidate hash changed since one or more opinions were recorded"
        items.append(
            _build_queue_item(
                candidate,
                adjudication_by_candidate.get(candidate_id),
                stale_reason=stale_reason,
            )
        )
    items.sort(key=lambda item: (item["queue_status"], item["candidate_id"]))
    return items


def _persist_projection_snapshot(workspace: Path, items: list[dict[str, Any]]) -> Path:
    root = _queue_root(workspace) / "projections"
    root.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "generated_at": utc_now(),
        "projection_version": PROJECTION_VERSION,
        "item_count": len(items),
        "items": items,
        "boundary": REVIEW_QUEUE_BOUNDARY,
    }
    digest = sha256_bytes(canonical_json_bytes(snapshot))
    path = safe_join(root, f"projection-{digest[:16]}.json")
    if not path.exists():
        atomic_write_json(path, snapshot)
    return path


def list_queue_items(workspace: Path, *, persist_projection: bool = False) -> list[dict[str, Any]]:
    items = rebuild_queue_projection(workspace)
    if persist_projection:
        _persist_projection_snapshot(workspace, items)
    leases = _active_leases_by_item(workspace)
    opinions = _opinions_by_item(workspace)
    enriched: list[dict[str, Any]] = []
    for item in items:
        copy = dict(item)
        copy["active_lease"] = leases.get(item["item_id"])
        copy["opinion_count"] = len(opinions.get(item["item_id"], []))
        copy["has_disagreement"] = any(
            opinion.get("position") == "OPPOSE" for opinion in opinions.get(item["item_id"], [])
        )
        enriched.append(copy)
    return enriched


def get_queue_item(workspace: Path, item_id: str) -> dict[str, Any]:
    ensure_identifier(item_id, "queue item ID")
    for item in list_queue_items(workspace):
        if item["item_id"] == item_id:
            return item
    raise ValueError(f"Unknown review queue item {item_id!r}")


def _load_leases(workspace: Path) -> list[dict[str, Any]]:
    return _load_records(_queue_root(workspace) / "leases")


def _load_lease_releases(workspace: Path) -> list[dict[str, Any]]:
    return _load_records(_queue_root(workspace) / "lease_releases")


def _released_lease_ids(workspace: Path) -> set[str]:
    return {str(item["lease_id"]) for item in _load_lease_releases(workspace)}


def _active_leases_by_item(workspace: Path, *, as_of: str | None = None) -> dict[str, dict[str, Any]]:
    now = _parse_timestamp(as_of or utc_now())
    released = _released_lease_ids(workspace)
    active: dict[str, dict[str, Any]] = {}
    for lease in _load_leases(workspace):
        lease_id = str(lease["lease_id"])
        if lease_id in released:
            continue
        if lease.get("lease_sha256") != _hash_record(lease, "lease_sha256"):
            continue
        expires_at = _parse_timestamp(str(lease["expires_at"]))
        if expires_at <= now:
            continue
        item_id = str(lease["item_id"])
        current = active.get(item_id)
        if current is None or str(lease["claimed_at"]) > str(current["claimed_at"]):
            active[item_id] = lease
    return active


def claim_lease(
    workspace: Path,
    item_id: str,
    reviewer_profile_id: str,
    *,
    ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
    actor: str | None = None,
) -> dict[str, Any]:
    ensure_identifier(item_id, "queue item ID")
    ensure_identifier(reviewer_profile_id, "reviewer profile ID")
    actor = actor or reviewer_profile_id
    ensure_identifier(actor, "actor ID")
    if ttl_seconds <= 0 or ttl_seconds > MAX_LEASE_TTL_SECONDS:
        raise ValueError(f"ttl_seconds must be between 1 and {MAX_LEASE_TTL_SECONDS}")

    _load_profile(workspace, reviewer_profile_id)
    item = get_queue_item(workspace, item_id)
    active = _active_leases_by_item(workspace)
    current = active.get(item_id)
    if current is not None:
        holder = str(current["reviewer_profile_id"])
        if holder != reviewer_profile_id:
            raise ValueError(f"Item {item_id!r} is already leased to profile {holder!r}; lease stealing is refused")
        raise ValueError(f"Profile {reviewer_profile_id!r} already holds an active lease on {item_id!r}")

    claimed_at = utc_now()
    expires_at = (_parse_timestamp(claimed_at) + timedelta(seconds=ttl_seconds)).isoformat().replace("+00:00", "Z")
    lease_id = f"RQL-{uuid4().hex}"
    record = {
        "lease_id": lease_id,
        "item_id": item_id,
        "reviewer_profile_id": reviewer_profile_id,
        "claimed_at": claimed_at,
        "expires_at": expires_at,
        "authority_profile": "LOCAL_UNAUTHENTICATED_ATTRIBUTION",
        "identity_boundary": IDENTITY_BOUNDARY,
        "boundary": REVIEW_QUEUE_BOUNDARY,
    }
    record["lease_sha256"] = _hash_record(record, "lease_sha256")
    errors = _schema_errors(record, LEASE_SCHEMA)
    if errors:
        raise ValueError(f"Review lease failed validation: {json.dumps(errors, ensure_ascii=False)}")

    output = safe_join(_queue_root(workspace) / "leases", f"{lease_id}.json")
    if output.exists():
        raise ValueError(f"Refusing to overwrite an existing lease record: {lease_id}")
    atomic_write_json(output, record)
    append_event(
        _events_path(workspace),
        "REVIEW_LEASE_CLAIMED",
        actor,
        {
            "lease_id": lease_id,
            "item_id": item_id,
            "reviewer_profile_id": reviewer_profile_id,
            "monitoring_record_sha256": item["monitoring_record_sha256"],
        },
    )
    return {"lease": record, "path": str(output)}


def release_lease(
    workspace: Path,
    lease_id: str,
    reviewer_profile_id: str,
    *,
    reason: str = "RELEASED",
    actor: str | None = None,
) -> dict[str, Any]:
    ensure_identifier(lease_id, "lease ID")
    ensure_identifier(reviewer_profile_id, "reviewer profile ID")
    actor = actor or reviewer_profile_id
    ensure_identifier(actor, "actor ID")
    if reason not in RELEASE_REASONS:
        raise ValueError(f"Unsupported release reason {reason!r}")

    lease_path = safe_join(_queue_root(workspace) / "leases", f"{lease_id}.json")
    if not lease_path.is_file():
        raise ValueError(f"Unknown lease {lease_id!r}")
    lease = cast(dict[str, Any], load_json(lease_path))
    if lease.get("lease_sha256") != _hash_record(lease, "lease_sha256"):
        raise ValueError(f"Lease {lease_id!r} has an invalid hash")
    if lease.get("reviewer_profile_id") != reviewer_profile_id:
        raise ValueError(
            f"Profile {reviewer_profile_id!r} cannot release lease {lease_id!r} held by "
            f"{lease.get('reviewer_profile_id')!r}"
        )
    if lease_id in _released_lease_ids(workspace):
        raise ValueError(f"Lease {lease_id!r} is already released")

    release_id = f"RLR-{uuid4().hex}"
    record = {
        "release_id": release_id,
        "lease_id": lease_id,
        "item_id": lease["item_id"],
        "reviewer_profile_id": reviewer_profile_id,
        "released_at": utc_now(),
        "release_reason": reason,
        "boundary": REVIEW_QUEUE_BOUNDARY,
    }
    record["release_sha256"] = _hash_record(record, "release_sha256")
    errors = _schema_errors(record, LEASE_RELEASE_SCHEMA)
    if errors:
        raise ValueError(f"Lease release failed validation: {json.dumps(errors, ensure_ascii=False)}")

    output = safe_join(_queue_root(workspace) / "lease_releases", f"{release_id}.json")
    if output.exists():
        raise ValueError(f"Refusing to overwrite an existing lease release record: {release_id}")
    atomic_write_json(output, record)
    append_event(
        _events_path(workspace),
        "REVIEW_LEASE_RELEASED",
        actor,
        {"lease_id": lease_id, "release_id": release_id, "release_reason": reason},
    )
    return {"release": record, "path": str(output)}


def _load_opinions(workspace: Path) -> list[dict[str, Any]]:
    return _load_records(_queue_root(workspace) / "opinions")


def _opinions_by_item(workspace: Path) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for opinion in _load_opinions(workspace):
        item_id = str(opinion["item_id"])
        grouped.setdefault(item_id, []).append(opinion)
    for opinions in grouped.values():
        opinions.sort(key=lambda item: str(item.get("submitted_at", "")))
    return grouped


def load_item_opinions(workspace: Path, item_id: str) -> list[dict[str, Any]]:
    ensure_identifier(item_id, "queue item ID")
    return list(_opinions_by_item(workspace).get(item_id, []))


def submit_opinion(
    workspace: Path,
    item_id: str,
    reviewer_profile_id: str,
    position: str,
    rationale: str,
    *,
    role: str | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    ensure_identifier(item_id, "queue item ID")
    ensure_identifier(reviewer_profile_id, "reviewer profile ID")
    actor = actor or reviewer_profile_id
    ensure_identifier(actor, "actor ID")
    if position not in OPINION_POSITIONS:
        raise ValueError(f"Unsupported opinion position {position!r}")
    rationale = rationale.strip()
    if not rationale:
        raise ValueError("Opinion rationale must not be empty")

    profile = _load_profile(workspace, reviewer_profile_id)
    selected_role = role or profile["roles"][0]
    if selected_role not in profile["roles"]:
        raise ValueError(f"Profile {reviewer_profile_id!r} does not include role {selected_role!r}")

    item = get_queue_item(workspace, item_id)
    active = _active_leases_by_item(workspace).get(item_id)
    if active is None or active.get("reviewer_profile_id") != reviewer_profile_id:
        raise ValueError(
            f"Profile {reviewer_profile_id!r} must hold an active lease on {item_id!r} before submitting an opinion"
        )

    candidate_id = _candidate_id_from_item(item_id)
    candidate_path = safe_join(_monitoring_root(workspace) / "candidates", f"{candidate_id}.json")
    before_candidate_hash = sha256_file(candidate_path)

    opinion_id = f"RQO-{uuid4().hex}"
    record = {
        "opinion_id": opinion_id,
        "item_id": item_id,
        "reviewer_profile_id": reviewer_profile_id,
        "role": selected_role,
        "position": position,
        "rationale": rationale,
        "monitoring_record_sha256": item["monitoring_record_sha256"],
        "submitted_at": utc_now(),
        "lease_id": active["lease_id"],
        "canonical_mutation_performed": False,
        "authority_profile": "LOCAL_UNAUTHENTICATED_ATTRIBUTION",
        "identity_boundary": IDENTITY_BOUNDARY,
        "boundary": REVIEW_QUEUE_BOUNDARY,
    }
    record["opinion_sha256"] = _hash_record(record, "opinion_sha256")
    errors = _schema_errors(record, OPINION_SCHEMA)
    if errors:
        raise ValueError(f"Review opinion failed validation: {json.dumps(errors, ensure_ascii=False)}")

    output = safe_join(_queue_root(workspace) / "opinions", f"{opinion_id}.json")
    if output.exists():
        raise ValueError(f"Refusing to overwrite an existing opinion record: {opinion_id}")
    atomic_write_json(output, record)

    after_candidate_hash = sha256_file(candidate_path)
    if before_candidate_hash != after_candidate_hash:
        raise RuntimeError("Candidate record changed during opinion submission; this must never occur")

    append_event(
        _events_path(workspace),
        "REVIEW_OPINION_SUBMITTED",
        actor,
        {
            "opinion_id": opinion_id,
            "item_id": item_id,
            "position": position,
            "opinion_sha256": record["opinion_sha256"],
        },
    )
    return {"opinion": record, "path": str(output)}


def verify_review_queue(workspace: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    root = _queue_root(workspace)
    if not root.is_dir():
        return {
            "valid": False,
            "errors": ["review queue is not initialized"],
            "warnings": [],
            "counts": {},
            "boundary": REVIEW_QUEUE_BOUNDARY,
        }

    try:
        _require_monitoring(workspace)
    except ValueError as exc:
        errors.append(str(exc))

    profiles = load_reviewer_profiles(workspace)
    for profile in profiles:
        profile_id = str(profile.get("profile_id"))
        if profile.get("profile_sha256") != _hash_record(profile, "profile_sha256"):
            errors.append(f"profile {profile_id}: hash mismatch")
        if profile.get("authority_profile") != "LOCAL_UNAUTHENTICATED_ATTRIBUTION":
            errors.append(f"profile {profile_id}: unsupported authority profile")

    projection_items = {item["item_id"]: item for item in rebuild_queue_projection(workspace)}
    released = _released_lease_ids(workspace)
    active_leases = _active_leases_by_item(workspace)

    for lease in _load_leases(workspace):
        lease_id = str(lease.get("lease_id"))
        if lease.get("lease_sha256") != _hash_record(lease, "lease_sha256"):
            errors.append(f"lease {lease_id}: hash mismatch")
        item_id = str(lease.get("item_id"))
        if item_id not in projection_items:
            errors.append(f"lease {lease_id}: unknown queue item {item_id}")
        elif lease_id not in released and lease_id == active_leases.get(item_id, {}).get("lease_id"):
            if item_id in projection_items and projection_items[item_id]["queue_status"] == "STALE":
                warnings.append(f"lease {lease_id}: queue item {item_id} is stale")

    for release in _load_lease_releases(workspace):
        release_id = str(release.get("release_id"))
        if release.get("release_sha256") != _hash_record(release, "release_sha256"):
            errors.append(f"lease release {release_id}: hash mismatch")

    opinions = _load_opinions(workspace)
    stale_opinions = 0
    disagreements = 0
    for opinion in opinions:
        opinion_id = str(opinion.get("opinion_id"))
        if opinion.get("opinion_sha256") != _hash_record(opinion, "opinion_sha256"):
            errors.append(f"opinion {opinion_id}: hash mismatch")
        if opinion.get("canonical_mutation_performed") is not False:
            errors.append(f"opinion {opinion_id}: canonical mutation flag must remain false")
        item_id = str(opinion.get("item_id"))
        projected = projection_items.get(item_id)
        if projected is None:
            errors.append(f"opinion {opinion_id}: unknown queue item {item_id}")
            continue
        if opinion.get("monitoring_record_sha256") != projected["monitoring_record_sha256"]:
            stale_opinions += 1
            warnings.append(f"opinion {opinion_id}: monitoring record hash is stale")
        if opinion.get("position") == "OPPOSE":
            disagreements += 1

    event_report = verify_chain(_events_path(workspace))
    if not event_report["valid"]:
        errors.extend(f"event chain: {error}" for error in event_report["errors"])

    monitoring_before = monitoring_status(workspace)
    rebuild_queue_projection(workspace)
    monitoring_after = monitoring_status(workspace)
    if monitoring_before != monitoring_after:
        errors.append("rebuilding queue projection altered monitoring status")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "profiles": len(profiles),
            "projection_items": len(projection_items),
            "leases": len(_load_leases(workspace)),
            "lease_releases": len(_load_lease_releases(workspace)),
            "active_leases": len(active_leases),
            "opinions": len(opinions),
            "stale_opinions": stale_opinions,
            "disagreements": disagreements,
        },
        "event_chain_valid": event_report["valid"],
        "boundary": REVIEW_QUEUE_BOUNDARY,
    }


def render_queue_markdown(workspace: Path) -> str:
    verification = verify_review_queue(workspace)
    items = list_queue_items(workspace)
    opinions_by_item = _opinions_by_item(workspace)
    lines = [
        "# Observatory monitoring review queue",
        "",
        (
            "> This report projects monitoring candidates and records local workflow attribution. "
            "It does not authenticate reviewers or mutate canonical observatory or assessment records."
        ),
        "",
        "## State",
        "",
        f"- Integrity: `{'VALID' if verification['valid'] else 'INVALID'}`",
        f"- Projection items: {verification['counts'].get('projection_items', 0)}",
        f"- Active leases: {verification['counts'].get('active_leases', 0)}",
        f"- Opinions: {verification['counts'].get('opinions', 0)}",
        f"- Disagreements: {verification['counts'].get('disagreements', 0)}",
        f"- Stale opinions: {verification['counts'].get('stale_opinions', 0)}",
        "",
        "## Queue items",
        "",
        "| Item | Source | Status | Opinions | Active lease |",
        "|---|---|---|---|---|",
    ]
    for item in items:
        lease = item.get("active_lease") or {}
        lines.append(
            f"| {item['item_id']} | {item['source_id']} | {item['queue_status']} | "
            f"{item.get('opinion_count', 0)} | {lease.get('reviewer_profile_id', '-')} |"
        )
    lines.extend(["", "## Opinions", ""])
    if not opinions_by_item:
        lines.append("_No opinions recorded._")
    else:
        lines.extend(
            [
                "| Opinion | Item | Profile | Role | Position | Rationale |",
                "|---|---|---|---|---|---|",
            ]
        )
        for item_id, opinions in sorted(opinions_by_item.items()):
            for opinion in opinions:
                rationale = str(opinion.get("rationale", "")).replace("|", "\\|").replace("\n", " ")
                lines.append(
                    f"| {opinion.get('opinion_id')} | {item_id} | {opinion.get('reviewer_profile_id')} | "
                    f"{opinion.get('role')} | {opinion.get('position')} | {rationale} |"
                )
    if verification["errors"]:
        lines.extend(["", "## Integrity errors", ""])
        lines.extend(f"- {error}" for error in verification["errors"])
    if verification["warnings"]:
        lines.extend(["", "## Review-state warnings", ""])
        lines.extend(f"- {warning}" for warning in verification["warnings"])
    return "\n".join(lines) + "\n"


def review_queue_status(workspace: Path) -> dict[str, Any]:
    root = _queue_root(workspace)
    if not root.is_dir():
        return {"initialized": False, "boundary": REVIEW_QUEUE_BOUNDARY}
    items = rebuild_queue_projection(workspace)
    return {
        "initialized": True,
        "projection_version": PROJECTION_VERSION,
        "item_count": len(items),
        "open_item_count": sum(1 for item in items if item["queue_status"] == "OPEN"),
        "adjudicated_item_count": sum(1 for item in items if item["queue_status"] == "ADJUDICATED"),
        "profile_count": len(load_reviewer_profiles(workspace)),
        "active_lease_count": len(_active_leases_by_item(workspace)),
        "opinion_count": len(_load_opinions(workspace)),
        "boundary": REVIEW_QUEUE_BOUNDARY,
    }
