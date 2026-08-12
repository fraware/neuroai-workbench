from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .events import load_events, verify_chain
from .util import load_json
from .workspace import Workspace

LEGACY_DIAGNOSTIC_BOUNDARY = (
    "Legacy governance diagnostics classify record/event persistence bindings only. "
    "They do not authenticate actors, validate substantive governance, or confer release authority."
)


@dataclass(frozen=True)
class LegacyRecordSpec:
    directory: str
    id_field: str
    digest_field: str
    event_action: str


LEGACY_RECORD_SPECS = (
    LegacyRecordSpec("scopes", "scope_id", "manifest_sha256", "GOVERNANCE_SCOPE_RECORDED"),
    LegacyRecordSpec("opinions", "opinion_id", "opinion_sha256", "GOVERNANCE_REVIEWER_OPINION_RECORDED"),
    LegacyRecordSpec("dispositions", "disposition_id", "disposition_sha256", "GOVERNANCE_OWNER_DISPOSITION_RECORDED"),
)


def _governance_root(workspace: Workspace) -> Path:
    return workspace.root / "governance"


def _matching_events(
    events: list[dict[str, Any]],
    *,
    action: str,
    id_field: str,
    record_id: str,
    digest_field: str,
    digest: str,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for event in events:
        payload = event.get("payload")
        if (
            event.get("action") == action
            and isinstance(payload, dict)
            and payload.get(id_field) == record_id
            and payload.get(digest_field) == digest
        ):
            matches.append(event)
    return matches


def diagnose_legacy_governance_bindings(workspace: Workspace) -> dict[str, Any]:
    """Classify existing governance records without rewriting historical bytes."""
    events_path = workspace.root / "events.jsonl"
    chain = verify_chain(events_path)
    if not chain.get("valid") or chain.get("trailer_valid") is not True:
        return {
            "valid": False,
            "records": [],
            "counts": {},
            "errors": ["Event chain is not fully valid; legacy governance diagnosis is blocked"],
            "release_authorization_performed": False,
            "boundary": LEGACY_DIAGNOSTIC_BOUNDARY,
        }
    events = load_events(events_path)
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    counts = {
        "LEGACY_BOUND": 0,
        "TRANSACTION_BOUND": 0,
        "ORPHAN": 0,
        "AMBIGUOUS": 0,
        "INVALID_RECORD": 0,
    }

    for spec in LEGACY_RECORD_SPECS:
        directory = _governance_root(workspace) / spec.directory
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            value = load_json(path)
            if not isinstance(value, dict):
                counts["INVALID_RECORD"] += 1
                errors.append(f"{path}: governance record must be an object")
                records.append({"path": str(path), "classification": "INVALID_RECORD"})
                continue
            record_id = value.get(spec.id_field)
            digest = value.get(spec.digest_field)
            if not isinstance(record_id, str) or not record_id or not isinstance(digest, str) or not digest:
                counts["INVALID_RECORD"] += 1
                errors.append(f"{path}: missing {spec.id_field} or {spec.digest_field}")
                records.append({"path": str(path), "classification": "INVALID_RECORD"})
                continue
            matches = _matching_events(
                events,
                action=spec.event_action,
                id_field=spec.id_field,
                record_id=record_id,
                digest_field=spec.digest_field,
                digest=digest,
            )
            if len(matches) == 0:
                classification = "ORPHAN"
                errors.append(f"{spec.directory}/{path.name}: no exact event binding")
            elif len(matches) > 1:
                classification = "AMBIGUOUS"
                errors.append(f"{spec.directory}/{path.name}: multiple exact event bindings")
            else:
                payload = matches[0].get("payload")
                classification = (
                    "TRANSACTION_BOUND"
                    if isinstance(payload, dict) and isinstance(payload.get("transaction_id"), str)
                    else "LEGACY_BOUND"
                )
            counts[classification] += 1
            records.append(
                {
                    "record_type": spec.directory.rstrip("s").upper(),
                    "record_id": record_id,
                    "record_sha256": digest,
                    "path": str(path),
                    "classification": classification,
                    "matching_event_count": len(matches),
                }
            )

    return {
        "valid": not errors,
        "records": records,
        "counts": counts,
        "errors": errors,
        "event_chain_head": chain.get("head_hash"),
        "release_authorization_performed": False,
        "boundary": LEGACY_DIAGNOSTIC_BOUNDARY,
    }
