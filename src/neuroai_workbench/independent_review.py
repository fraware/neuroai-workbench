from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from jsonschema import Draft202012Validator

from .events import append_event, verify_chain
from .util import (
    atomic_write_json,
    canonical_json_bytes,
    ensure_identifier,
    load_json,
    sha256_bytes,
    sha256_file,
    utc_now,
)
from .workspace import Workspace

OPERATIONS_RESOURCE_PACKAGE = "neuroai_workbench.resources.operations"
DISPOSITION_SCHEMA = "INDEPENDENT_REVIEW_DISPOSITION.schema.json"
SCHEMA_VERSION = "1"

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
DISPOSITIONS = frozenset(
    {
        "ACCEPTED",
        "ACCEPTED_WITH_CONDITIONS",
        "REJECTED",
        "DEFERRED",
        "INCOMPLETE",
    }
)

INDEPENDENT_REVIEW_BOUNDARY = (
    "Independent review disposition records attribute a claimed local review outcome. "
    "They do not authenticate reviewers, establish institutional authority, authorize release, "
    "or convert review completion into scientific, regulatory, security-acceptance, or conformance truth."
)


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


def _hash_record(value: dict[str, Any]) -> str:
    controlled = {key: item for key, item in value.items() if key != "disposition_sha256" and not key.startswith("_")}
    return sha256_bytes(canonical_json_bytes(controlled))


def _dispositions_root(workspace: Workspace) -> Path:
    root = workspace.root / "independent_reviews" / "dispositions"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _load_disposition_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        value = load_json(path)
        if isinstance(value, dict):
            record = cast(dict[str, Any], value)
            record["_path"] = str(path)
            records.append(record)
    return records


def record_independent_review_disposition(
    workspace: Workspace,
    review_track: str,
    scope_label: str,
    scope_sha256: str,
    disposition: str,
    reviewer_claim: dict[str, Any],
    rationale: str,
    *,
    recorded_by: str = "local-user",
    conditions: list[str] | None = None,
    findings_register_ref: str | None = None,
    unresolved_risks: list[str] | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    """Record an append-only independent review disposition without authorizing release."""
    ensure_identifier(recorded_by, "recorded_by")
    actor = actor or recorded_by
    ensure_identifier(actor, "actor")
    if review_track not in REVIEW_TRACKS:
        raise ValueError(f"Unsupported independent review track {review_track!r}")
    if disposition not in DISPOSITIONS:
        raise ValueError(f"Unsupported independent review disposition {disposition!r}")
    normalized_conditions = sorted({item.strip() for item in (conditions or []) if item.strip()})
    if disposition == "ACCEPTED_WITH_CONDITIONS" and not normalized_conditions:
        raise ValueError("ACCEPTED_WITH_CONDITIONS requires at least one condition")
    rationale = rationale.strip()
    if not rationale:
        raise ValueError("Independent review rationale must not be empty")
    if not isinstance(reviewer_claim, dict):
        raise ValueError("reviewer_claim must be an object")
    for field in ("name_or_role", "accountability_state", "independence_statement"):
        if not str(reviewer_claim.get(field, "")).strip():
            raise ValueError(f"reviewer_claim.{field} is required")
    if (
        not isinstance(scope_sha256, str)
        or len(scope_sha256) != 64
        or any(ch not in "0123456789abcdef" for ch in scope_sha256)
    ):
        raise ValueError("scope_sha256 must be a 64-character lowercase hexadecimal digest")

    disposition_id = f"IRD-{uuid4().hex}"
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "disposition_id": disposition_id,
        "review_track": review_track,
        "scope_label": scope_label.strip(),
        "scope_sha256": scope_sha256,
        "disposition": disposition,
        "reviewer_claim": {
            "name_or_role": str(reviewer_claim["name_or_role"]).strip(),
            "accountability_state": str(reviewer_claim["accountability_state"]).strip(),
            "independence_statement": str(reviewer_claim["independence_statement"]).strip(),
            **(
                {"organization": str(reviewer_claim["organization"]).strip()}
                if reviewer_claim.get("organization")
                else {}
            ),
            **(
                {"conflict_of_interest_disclosure": str(reviewer_claim["conflict_of_interest_disclosure"]).strip()}
                if reviewer_claim.get("conflict_of_interest_disclosure")
                else {}
            ),
        },
        "recorded_at": utc_now(),
        "recorded_by": recorded_by,
        "rationale": rationale,
        "release_authorization_performed": False,
        "authority_profile": "LOCAL_UNAUTHENTICATED_ATTRIBUTION",
        "boundary": INDEPENDENT_REVIEW_BOUNDARY,
    }
    if normalized_conditions:
        record["conditions"] = normalized_conditions
    if findings_register_ref:
        record["findings_register_ref"] = findings_register_ref.strip()
    if unresolved_risks:
        record["unresolved_risks"] = sorted({item.strip() for item in unresolved_risks if item.strip()})
    record["disposition_sha256"] = _hash_record(record)

    errors = _schema_errors(record, DISPOSITION_SCHEMA)
    if errors:
        raise ValueError(f"Independent review disposition failed validation: {json.dumps(errors, ensure_ascii=False)}")

    output = _dispositions_root(workspace) / f"{disposition_id}.json"
    if output.exists():
        raise ValueError(f"An independent review disposition already exists: {disposition_id}")
    atomic_write_json(output, record)
    append_event(
        workspace.root / "events.jsonl",
        "INDEPENDENT_REVIEW_DISPOSITION_RECORDED",
        actor,
        {
            "disposition_id": disposition_id,
            "review_track": review_track,
            "scope_label": scope_label,
            "disposition": disposition,
            "disposition_sha256": record["disposition_sha256"],
            "release_authorization_performed": False,
        },
    )
    return {"disposition": record, "path": str(output)}


def scope_sha256_for_path(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"Scope artifact does not exist: {path}")
    return sha256_file(path)


def load_independent_review_dispositions(workspace: Workspace) -> list[dict[str, Any]]:
    return _load_disposition_records(_dispositions_root(workspace))


def verify_independent_review_dispositions(workspace: Workspace) -> dict[str, Any]:
    records = load_independent_review_dispositions(workspace)
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    tracks: dict[str, list[str]] = {track: [] for track in sorted(REVIEW_TRACKS)}

    for item in records:
        disposition_id = str(item.get("disposition_id"))
        schema_target = {key: value for key, value in item.items() if not key.startswith("_")}
        if disposition_id in seen_ids:
            errors.append(f"disposition {disposition_id}: duplicate disposition_id")
        seen_ids.add(disposition_id)
        if item.get("disposition_sha256") != _hash_record(schema_target):
            errors.append(f"disposition {disposition_id}: hash mismatch")
        if _schema_errors(schema_target, DISPOSITION_SCHEMA):
            errors.append(f"disposition {disposition_id}: schema invalid")
        if item.get("review_track") not in REVIEW_TRACKS:
            errors.append(f"disposition {disposition_id}: unsupported review track")
        if item.get("disposition") not in DISPOSITIONS:
            errors.append(f"disposition {disposition_id}: unsupported disposition")
        if item.get("release_authorization_performed") is not False:
            errors.append(f"disposition {disposition_id}: release authorization must remain false")
        track = str(item.get("review_track"))
        if track in tracks:
            tracks[track].append(disposition_id)
        if item.get("disposition") == "ACCEPTED_WITH_CONDITIONS" and not item.get("conditions"):
            errors.append(f"disposition {disposition_id}: conditions required for ACCEPTED_WITH_CONDITIONS")

    event_report = verify_chain(workspace.root / "events.jsonl")
    if not event_report["valid"]:
        errors.extend(f"event chain: {error}" for error in event_report["errors"])

    missing_tracks = sorted(track for track, ids in tracks.items() if not ids)
    if missing_tracks:
        warnings.append(f"No disposition recorded for review tracks: {', '.join(missing_tracks)}")

    return {
        "valid": not errors,
        "counts": {
            "dispositions": len(records),
            "tracks_with_records": sum(1 for ids in tracks.values() if ids),
            "missing_tracks": len(missing_tracks),
        },
        "tracks": tracks,
        "errors": errors,
        "warnings": warnings,
        "event_chain_valid": event_report["valid"],
        "release_authorization_performed": False,
        "boundary": INDEPENDENT_REVIEW_BOUNDARY,
    }


def summarize_independent_review_acceptance(workspace: Workspace) -> dict[str, Any]:
    verification = verify_independent_review_dispositions(workspace)
    latest_by_track: dict[str, dict[str, Any]] = {}
    for item in load_independent_review_dispositions(workspace):
        track = str(item.get("review_track"))
        current = latest_by_track.get(track)
        if current is None or str(item.get("recorded_at", "")) >= str(current.get("recorded_at", "")):
            latest_by_track[track] = item

    incomplete_tracks = sorted(
        track
        for track in REVIEW_TRACKS
        if track not in latest_by_track
        or latest_by_track[track].get("disposition") in {"REJECTED", "DEFERRED", "INCOMPLETE"}
    )
    return {
        "integrity_valid": verification["valid"],
        "tracks_complete": len(incomplete_tracks) == 0,
        "incomplete_tracks": incomplete_tracks,
        "latest_by_track": {
            track: {
                "disposition_id": item.get("disposition_id"),
                "disposition": item.get("disposition"),
                "scope_label": item.get("scope_label"),
                "recorded_at": item.get("recorded_at"),
            }
            for track, item in sorted(latest_by_track.items())
        },
        "release_authorization_performed": False,
        "institutional_pilot_readiness_established": False,
        "release_gate_blocked": False,
        "boundary": (
            "Independent review track completeness is optional documentation status only. "
            "Incomplete tracks do not block AUTHORIZED or PUBLISHED successor release gates. "
            "Disposition integrity still does not authorize release, establish pilot readiness, "
            "or imply UNESCO, regulatory, clinical, or conformance authority."
        ),
    }
