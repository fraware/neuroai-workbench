from __future__ import annotations

import json
from collections import Counter, defaultdict
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any, cast
from uuid import uuid4

from jsonschema import Draft202012Validator

from .events import append_event, load_events, verify_chain
from .governance_scope import load_governance_scope_manifests
from .util import atomic_write_json, canonical_json_bytes, ensure_identifier, load_json, sha256_bytes, utc_now
from .workspace import Workspace

OPERATIONS_RESOURCE_PACKAGE = "neuroai_workbench.resources.operations"
OPINION_SCHEMA = "GOVERNANCE_REVIEWER_OPINION.schema.json"
SCHEMA_VERSION = "1"
RUNTIME_PRIVATE_KEYS = frozenset({"_path"})
PROTECTED_PREFIX = "protected-ref:"

REVIEW_TRACKS = frozenset(
    {
        "SECURITY",
        "METHODOLOGY",
        "DATA_GOVERNANCE",
        "ACCESSIBILITY",
        "DOMAIN",
        "AFFECTED_COMMUNITY",
    }
)
OPINION_STATES = frozenset(
    {
        "SUPPORT",
        "SUPPORT_WITH_CONDITIONS",
        "OBJECT",
        "ABSTAIN",
        "REQUEST_EVIDENCE",
    }
)
STORAGE_BOUNDARIES = frozenset({"PUBLIC_GIT", "GENERATED_OUTPUT", "PROTECTED_WORKSPACE", "ARCHIVE"})

GOVERNANCE_OPINION_BOUNDARY = (
    "Governance reviewer opinions preserve claimed attribution, disagreement, abstention, evidence requests, "
    "and supersession over an exact governance scope. Record integrity does not authenticate a reviewer, "
    "establish independence or institutional delegation, resolve substantive disputes, or authorize release."
)


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


def _hash_record(value: dict[str, Any]) -> str:
    controlled = {
        key: item for key, item in value.items() if key != "opinion_sha256" and key not in RUNTIME_PRIVATE_KEYS
    }
    return sha256_bytes(canonical_json_bytes(controlled))


def _scope_manifest_sha256(value: dict[str, Any]) -> str:
    controlled = {
        key: item for key, item in value.items() if key != "manifest_sha256" and key not in RUNTIME_PRIVATE_KEYS
    }
    return sha256_bytes(canonical_json_bytes(controlled))


def _opinions_root(workspace: Workspace) -> Path:
    root = workspace.root / "governance" / "opinions"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _validate_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a 64-character lowercase hexadecimal digest")
    return value


def _normalize_strings(values: list[str] | None) -> list[str]:
    return sorted({value.strip() for value in (values or []) if value.strip()})


def _validate_locator(storage_boundary: str, locator: str) -> None:
    if storage_boundary not in STORAGE_BOUNDARIES:
        raise ValueError(f"Unsupported evidence storage boundary {storage_boundary!r}")
    if not locator:
        raise ValueError("Evidence locator must not be empty")
    if storage_boundary == "PROTECTED_WORKSPACE":
        if not locator.startswith(PROTECTED_PREFIX):
            raise ValueError("Protected evidence references require an opaque protected-ref locator")
        ensure_identifier(locator.removeprefix(PROTECTED_PREFIX), "protected evidence reference")
        return
    if locator.startswith(PROTECTED_PREFIX):
        raise ValueError("Opaque protected-ref locators are reserved for PROTECTED_WORKSPACE evidence")
    if "\\" in locator:
        raise ValueError("Evidence locators must use POSIX separators")
    pure = PurePosixPath(locator)
    if pure.is_absolute() or pure.as_posix() != locator or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("Evidence locator must be a normalized relative POSIX path")


def _normalize_evidence_references(values: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for index, item in enumerate(values or []):
        if not isinstance(item, dict):
            raise ValueError(f"evidence_references.{index} must be an object")
        label = str(item.get("label", "")).strip()
        if not label:
            raise ValueError(f"evidence_references.{index}.label is required")
        digest = _validate_sha256(item.get("sha256"), f"evidence_references.{index}.sha256")
        storage_boundary = str(item.get("storage_boundary", ""))
        locator = str(item.get("locator", ""))
        _validate_locator(storage_boundary, locator)
        key = (label, digest, storage_boundary, locator)
        if key in seen:
            raise ValueError(f"evidence_references.{index} duplicates an earlier reference")
        seen.add(key)
        normalized.append(
            {
                "label": label,
                "sha256": digest,
                "storage_boundary": storage_boundary,
                "locator": locator,
            }
        )
    return sorted(
        normalized,
        key=lambda item: (
            item["storage_boundary"],
            item["locator"],
            item["sha256"],
            item["label"],
        ),
    )


def _load_opinion_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        value = load_json(path)
        if isinstance(value, dict):
            record = cast(dict[str, Any], value)
            record["_path"] = str(path)
            records.append(record)
    return records


def load_governance_reviewer_opinions(workspace: Workspace) -> list[dict[str, Any]]:
    return _load_opinion_records(_opinions_root(workspace))


def _scope_records_by_id(workspace: Workspace) -> dict[str, dict[str, Any]]:
    scopes: dict[str, dict[str, Any]] = {}
    for scope in load_governance_scope_manifests(workspace):
        scope_id = str(scope.get("scope_id", ""))
        if not scope_id:
            raise ValueError("Governance scope record is missing scope_id")
        unsupported_private = sorted(key for key in scope if key.startswith("_") and key not in RUNTIME_PRIVATE_KEYS)
        if unsupported_private:
            raise ValueError(f"Governance scope {scope_id} contains unsupported private fields {unsupported_private}")
        if scope.get("manifest_sha256") != _scope_manifest_sha256(scope):
            raise ValueError(f"Governance scope {scope_id} failed canonical hash verification")
        if scope.get("release_authorization_performed") is not False:
            raise ValueError(f"Governance scope {scope_id} must remain non-authorizing")
        if scope_id in scopes:
            raise ValueError(f"Duplicate governance scope ID {scope_id}")
        scopes[scope_id] = scope
    return scopes


def _record_index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        opinion_id = str(record.get("opinion_id", ""))
        if opinion_id in index:
            raise ValueError(f"Duplicate governance opinion ID {opinion_id}")
        index[opinion_id] = record
    return index


def _active_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    superseded = {str(record.get("supersedes_opinion_id")) for record in records if record.get("supersedes_opinion_id")}
    return [record for record in records if str(record.get("opinion_id")) not in superseded]


def record_governance_reviewer_opinion(
    workspace: Workspace,
    *,
    scope_id: str,
    scope_sha256: str,
    review_track: str,
    opinion_state: str,
    reviewer_claim: dict[str, Any],
    rationale: str,
    recorded_by: str = "local-user",
    conditions: list[str] | None = None,
    evidence_requests: list[str] | None = None,
    evidence_references: list[dict[str, Any]] | None = None,
    supersedes_opinion_id: str | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    """Record one append-only, non-authorizing reviewer opinion."""
    ensure_identifier(recorded_by, "recorded_by")
    actor = actor or recorded_by
    ensure_identifier(actor, "actor")
    ensure_identifier(scope_id, "scope_id")
    scope_sha256 = _validate_sha256(scope_sha256, "scope_sha256")
    if review_track not in REVIEW_TRACKS:
        raise ValueError(f"Unsupported governance review track {review_track!r}")
    if opinion_state not in OPINION_STATES:
        raise ValueError(f"Unsupported governance opinion state {opinion_state!r}")
    rationale = rationale.strip()
    if not rationale:
        raise ValueError("Governance reviewer opinion rationale must not be empty")
    if not isinstance(reviewer_claim, dict):
        raise ValueError("reviewer_claim must be an object")

    reviewer_key = str(reviewer_claim.get("reviewer_key", "")).strip()
    ensure_identifier(reviewer_key, "reviewer_claim.reviewer_key")
    required_claim_fields = (
        "name_or_role",
        "accountability_state",
        "independence_statement",
        "conflict_of_interest_disclosure",
    )
    for field in required_claim_fields:
        if not str(reviewer_claim.get(field, "")).strip():
            raise ValueError(f"reviewer_claim.{field} is required")

    normalized_conditions = _normalize_strings(conditions)
    normalized_requests = _normalize_strings(evidence_requests)
    normalized_references = _normalize_evidence_references(evidence_references)
    if opinion_state == "SUPPORT_WITH_CONDITIONS" and not normalized_conditions:
        raise ValueError("SUPPORT_WITH_CONDITIONS requires at least one condition")
    if opinion_state == "REQUEST_EVIDENCE" and not normalized_requests:
        raise ValueError("REQUEST_EVIDENCE requires at least one evidence request")

    scopes = _scope_records_by_id(workspace)
    scope = scopes.get(scope_id)
    if scope is None:
        raise ValueError(f"Governance scope {scope_id} does not exist")
    if scope.get("manifest_sha256") != scope_sha256:
        raise ValueError(f"Governance scope {scope_id} SHA-256 does not match the recorded manifest")

    existing = load_governance_reviewer_opinions(workspace)
    if existing:
        existing_verification = verify_governance_reviewer_opinions(workspace)
        if not existing_verification["valid"]:
            raise ValueError(
                "Existing governance opinion store failed verification: "
                f"{json.dumps(existing_verification['errors'], ensure_ascii=False)}"
            )
    index = _record_index(existing)
    matching_active = [
        record
        for record in _active_records(existing)
        if record.get("scope_id") == scope_id
        and record.get("review_track") == review_track
        and isinstance(record.get("reviewer_claim"), dict)
        and record["reviewer_claim"].get("reviewer_key") == reviewer_key
    ]
    if supersedes_opinion_id is None and matching_active:
        raise ValueError(
            "An active opinion already exists for this reviewer, track, and scope; explicit supersession is required"
        )
    superseded: dict[str, Any] | None = None
    if supersedes_opinion_id is not None:
        ensure_identifier(supersedes_opinion_id, "supersedes_opinion_id")
        superseded = index.get(supersedes_opinion_id)
        if superseded is None:
            raise ValueError(f"Superseded opinion {supersedes_opinion_id} does not exist")
        if not matching_active or matching_active[0].get("opinion_id") != supersedes_opinion_id:
            raise ValueError(
                "supersedes_opinion_id must identify the current active opinion for this reviewer and track"
            )
        if superseded.get("opinion_sha256") != _hash_record(superseded):
            raise ValueError(f"Superseded opinion {supersedes_opinion_id} failed hash verification")

    opinion_id = f"GOVOP-{uuid4().hex}"
    claim: dict[str, str] = {
        "reviewer_key": reviewer_key,
        "name_or_role": str(reviewer_claim["name_or_role"]).strip(),
        "accountability_state": str(reviewer_claim["accountability_state"]).strip(),
        "independence_statement": str(reviewer_claim["independence_statement"]).strip(),
        "conflict_of_interest_disclosure": str(reviewer_claim["conflict_of_interest_disclosure"]).strip(),
    }
    if reviewer_claim.get("organization"):
        claim["organization"] = str(reviewer_claim["organization"]).strip()

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "opinion_id": opinion_id,
        "scope_id": scope_id,
        "scope_sha256": scope_sha256,
        "review_track": review_track,
        "opinion_state": opinion_state,
        "reviewer_claim": claim,
        "recorded_at": utc_now(),
        "recorded_by": recorded_by,
        "rationale": rationale,
        "release_authorization_performed": False,
        "authority_profile": "CLAIMED_REVIEW_ATTRIBUTION",
        "boundary": GOVERNANCE_OPINION_BOUNDARY,
    }
    if normalized_conditions:
        record["conditions"] = normalized_conditions
    if normalized_requests:
        record["evidence_requests"] = normalized_requests
    if normalized_references:
        record["evidence_references"] = normalized_references
    if superseded is not None:
        record["supersedes_opinion_id"] = supersedes_opinion_id
        record["supersedes_opinion_sha256"] = str(superseded["opinion_sha256"])
    record["opinion_sha256"] = _hash_record(record)

    errors = _schema_errors(record, OPINION_SCHEMA)
    if errors:
        raise ValueError(f"Governance reviewer opinion failed validation: {json.dumps(errors, ensure_ascii=False)}")

    output = _opinions_root(workspace) / f"{opinion_id}.json"
    if output.exists():
        raise ValueError(f"A governance reviewer opinion already exists: {opinion_id}")
    atomic_write_json(output, record)
    append_event(
        workspace.root / "events.jsonl",
        "GOVERNANCE_REVIEWER_OPINION_RECORDED",
        actor,
        {
            "opinion_id": opinion_id,
            "opinion_sha256": record["opinion_sha256"],
            "scope_id": scope_id,
            "scope_sha256": scope_sha256,
            "review_track": review_track,
            "opinion_state": opinion_state,
            "reviewer_key": reviewer_key,
            "supersedes_opinion_id": supersedes_opinion_id,
            "release_authorization_performed": False,
        },
    )
    return {"opinion": record, "path": str(output)}


def _supersession_errors(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    try:
        index = _record_index(records)
    except ValueError as exc:
        return [str(exc)]
    superseders: dict[str, list[str]] = defaultdict(list)
    graph: dict[str, str] = {}

    for record in records:
        opinion_id = str(record.get("opinion_id", ""))
        target_id = record.get("supersedes_opinion_id")
        target_sha = record.get("supersedes_opinion_sha256")
        if target_id is None and target_sha is None:
            continue
        if not isinstance(target_id, str) or not isinstance(target_sha, str):
            errors.append(f"opinion {opinion_id}: incomplete supersession reference")
            continue
        target = index.get(target_id)
        if target is None:
            errors.append(f"opinion {opinion_id}: superseded opinion {target_id} is missing")
            continue
        if target_id == opinion_id:
            errors.append(f"opinion {opinion_id}: an opinion cannot supersede itself")
        if target.get("opinion_sha256") != target_sha:
            errors.append(f"opinion {opinion_id}: superseded opinion hash mismatch")
        for field in ("scope_id", "scope_sha256", "review_track"):
            if target.get(field) != record.get(field):
                errors.append(f"opinion {opinion_id}: supersession changes {field}")
        reviewer = record.get("reviewer_claim")
        target_reviewer = target.get("reviewer_claim")
        reviewer_key = reviewer.get("reviewer_key") if isinstance(reviewer, dict) else None
        target_key = target_reviewer.get("reviewer_key") if isinstance(target_reviewer, dict) else None
        if reviewer_key != target_key:
            errors.append(f"opinion {opinion_id}: supersession changes reviewer_key")
        superseders[target_id].append(opinion_id)
        graph[opinion_id] = target_id

    for target_id, opinion_ids in sorted(superseders.items()):
        if len(opinion_ids) > 1:
            errors.append(f"opinion {target_id}: branching supersession by {', '.join(sorted(opinion_ids))}")

    for start in sorted(graph):
        seen: set[str] = set()
        current = start
        while current in graph:
            if current in seen:
                errors.append(f"opinion {start}: supersession cycle detected")
                break
            seen.add(current)
            current = graph[current]
    return errors


def verify_governance_reviewer_opinions(workspace: Workspace) -> dict[str, Any]:
    """Verify opinion integrity, governance-scope binding, supersession, events, and active uniqueness."""
    records = load_governance_reviewer_opinions(workspace)
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    try:
        scopes = _scope_records_by_id(workspace)
    except ValueError as exc:
        scopes = {}
        errors.append(f"governance scope store invalid: {exc}")

    try:
        events = load_events(workspace.root / "events.jsonl")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        events = []
        errors.append(f"event log load failed: {exc}")
    opinion_events: Counter[tuple[str, str, str, str]] = Counter(
        (
            str(event.get("payload", {}).get("opinion_id")),
            str(event.get("payload", {}).get("opinion_sha256")),
            str(event.get("payload", {}).get("scope_id")),
            str(event.get("payload", {}).get("scope_sha256")),
        )
        for event in events
        if event.get("action") == "GOVERNANCE_REVIEWER_OPINION_RECORDED" and isinstance(event.get("payload"), dict)
    )

    for record in records:
        opinion_id = str(record.get("opinion_id", ""))
        if opinion_id in seen_ids:
            errors.append(f"opinion {opinion_id}: duplicate opinion_id")
        seen_ids.add(opinion_id)
        unsupported_private = sorted(key for key in record if key.startswith("_") and key not in RUNTIME_PRIVATE_KEYS)
        if unsupported_private:
            errors.append(f"opinion {opinion_id}: unsupported private fields {unsupported_private}")
        schema_target = {key: value for key, value in record.items() if key not in RUNTIME_PRIVATE_KEYS}
        if record.get("opinion_sha256") != _hash_record(record):
            errors.append(f"opinion {opinion_id}: hash mismatch")
        if _schema_errors(schema_target, OPINION_SCHEMA):
            errors.append(f"opinion {opinion_id}: schema invalid")
        if record.get("boundary") != GOVERNANCE_OPINION_BOUNDARY:
            errors.append(f"opinion {opinion_id}: authority boundary mismatch")
        if record.get("review_track") not in REVIEW_TRACKS:
            errors.append(f"opinion {opinion_id}: unsupported review track")
        if record.get("opinion_state") not in OPINION_STATES:
            errors.append(f"opinion {opinion_id}: unsupported opinion state")
        if record.get("release_authorization_performed") is not False:
            errors.append(f"opinion {opinion_id}: release authorization must remain false")
        if record.get("opinion_state") == "SUPPORT_WITH_CONDITIONS" and not record.get("conditions"):
            errors.append(f"opinion {opinion_id}: conditions required for SUPPORT_WITH_CONDITIONS")
        if record.get("opinion_state") == "REQUEST_EVIDENCE" and not record.get("evidence_requests"):
            errors.append(f"opinion {opinion_id}: evidence requests required for REQUEST_EVIDENCE")

        scope_id = str(record.get("scope_id", ""))
        scope = scopes.get(scope_id)
        if scope is None:
            errors.append(f"opinion {opinion_id}: governance scope {scope_id} is missing")
        elif scope.get("manifest_sha256") != record.get("scope_sha256"):
            errors.append(f"opinion {opinion_id}: governance scope hash mismatch")

        event_key = (
            opinion_id,
            str(record.get("opinion_sha256")),
            scope_id,
            str(record.get("scope_sha256")),
        )
        event_count = opinion_events[event_key]
        if event_count == 0:
            errors.append(f"opinion {opinion_id}: matching append-only event is missing")
        elif event_count > 1:
            errors.append(f"opinion {opinion_id}: {event_count} matching append-only events were recorded")

        references = record.get("evidence_references", [])
        if isinstance(references, list):
            for index, reference in enumerate(references):
                try:
                    if not isinstance(reference, dict):
                        raise ValueError("reference must be an object")
                    _validate_sha256(reference.get("sha256"), f"evidence_references.{index}.sha256")
                    _validate_locator(
                        str(reference.get("storage_boundary", "")),
                        str(reference.get("locator", "")),
                    )
                except ValueError as exc:
                    errors.append(f"opinion {opinion_id}: invalid evidence reference {index}: {exc}")

    errors.extend(_supersession_errors(records))

    active = _active_records(records)
    active_keys: Counter[tuple[str, str, str]] = Counter()
    tracks_with_active: set[str] = set()
    for record in active:
        reviewer = record.get("reviewer_claim")
        reviewer_key = str(reviewer.get("reviewer_key", "")) if isinstance(reviewer, dict) else ""
        key = (
            str(record.get("scope_id", "")),
            str(record.get("review_track", "")),
            reviewer_key,
        )
        active_keys[key] += 1
        tracks_with_active.add(str(record.get("review_track", "")))
    for key, count in sorted(active_keys.items()):
        if count > 1:
            errors.append(
                "multiple active opinions for scope, track, and reviewer: "
                f"scope={key[0]} track={key[1]} reviewer={key[2]}"
            )

    missing_tracks = sorted(REVIEW_TRACKS - tracks_with_active)
    if missing_tracks:
        warnings.append(f"No active opinion recorded for review tracks: {', '.join(missing_tracks)}")

    chain = verify_chain(workspace.root / "events.jsonl")
    if not chain["valid"] or not chain.get("trailer_valid", False):
        errors.extend(f"event chain: {error}" for error in chain["errors"])
        errors.extend(f"event chain trailer: {error}" for error in chain.get("trailer_errors", []))

    return {
        "valid": not errors,
        "counts": {
            "opinions": len(records),
            "active_opinions": len(active),
            "superseded_opinions": len(records) - len(active),
            "tracks_with_active_opinions": len(tracks_with_active),
            "missing_tracks": len(missing_tracks),
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "errors": errors,
        "warnings": warnings,
        "event_chain_valid": chain["valid"] and chain.get("trailer_valid", False),
        "release_authorization_performed": False,
        "boundary": GOVERNANCE_OPINION_BOUNDARY,
    }


def summarize_governance_reviewer_opinions(workspace: Workspace) -> dict[str, Any]:
    """Summarize active opinions without erasing dissent, abstention, or requests for evidence."""
    verification = verify_governance_reviewer_opinions(workspace)
    active = _active_records(load_governance_reviewer_opinions(workspace))
    by_track: dict[str, list[dict[str, Any]]] = {track: [] for track in sorted(REVIEW_TRACKS)}
    state_counts: Counter[str] = Counter()
    disagreement_tracks: list[str] = []

    for record in sorted(
        active,
        key=lambda item: (
            str(item.get("review_track", "")),
            str(item.get("reviewer_claim", {}).get("reviewer_key", ""))
            if isinstance(item.get("reviewer_claim"), dict)
            else "",
            str(item.get("recorded_at", "")),
            str(item.get("opinion_id", "")),
        ),
    ):
        track = str(record.get("review_track", ""))
        state = str(record.get("opinion_state", ""))
        state_counts[state] += 1
        if track in by_track:
            reviewer = record.get("reviewer_claim")
            reviewer_key = reviewer.get("reviewer_key") if isinstance(reviewer, dict) else None
            by_track[track].append(
                {
                    "opinion_id": record.get("opinion_id"),
                    "opinion_sha256": record.get("opinion_sha256"),
                    "scope_id": record.get("scope_id"),
                    "scope_sha256": record.get("scope_sha256"),
                    "reviewer_key": reviewer_key,
                    "opinion_state": state,
                    "conditions": record.get("conditions", []),
                    "evidence_requests": record.get("evidence_requests", []),
                    "recorded_at": record.get("recorded_at"),
                }
            )

    for track, opinions in by_track.items():
        states = {str(opinion["opinion_state"]) for opinion in opinions}
        has_support = bool(states & {"SUPPORT", "SUPPORT_WITH_CONDITIONS"})
        has_blocking = bool(states & {"OBJECT", "REQUEST_EVIDENCE"})
        if has_support and has_blocking:
            disagreement_tracks.append(track)

    return {
        "integrity_valid": verification["valid"],
        "scope_ids": sorted({str(record.get("scope_id")) for record in active}),
        "active_state_counts": dict(sorted(state_counts.items())),
        "by_track": by_track,
        "disagreement_present": bool(disagreement_tracks),
        "disagreement_tracks": disagreement_tracks,
        "objection_present": state_counts["OBJECT"] > 0,
        "evidence_request_present": state_counts["REQUEST_EVIDENCE"] > 0,
        "abstention_present": state_counts["ABSTAIN"] > 0,
        "conditions_present": state_counts["SUPPORT_WITH_CONDITIONS"] > 0,
        "release_authorization_performed": False,
        "release_readiness_established": False,
        "boundary": GOVERNANCE_OPINION_BOUNDARY,
    }
