from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .case_lock import case_mutation_lock
from .events import append_event, load_events, verify_chain
from .util import atomic_write_json, canonical_json_bytes, ensure_identifier, sha256_bytes, sha256_file
from .workspace import Workspace

REVIEW_SCHEMA_VERSION = "1"
REVIEW_ROLES = {
    "LEAD_ASSESSOR",
    "DECISION_AUTHORITY",
    "DOMAIN_REVIEWER",
    "METHODS_REVIEWER",
    "SECURITY_REVIEWER",
    "LEGAL_REGULATORY_REVIEWER",
    "PARTICIPANT_REPRESENTATIVE",
    "OBSERVER",
}
POSITIONS = {"AGREE", "AGREE_WITH_CONDITIONS", "DISAGREE", "ABSTAIN"}
DISPOSITIONS = {"ACCEPTED", "PARTIALLY_ACCEPTED", "REJECTED", "DEFERRED"}
TARGET_TYPES = {"ASSESSMENT", "FINDING", "CLAIM", "DECISION", "GAP"}
DECISION_ROLES = {"LEAD_ASSESSOR", "DECISION_AUTHORITY"}
ASSIGNMENT_STATES = {"ACTIVE", "REVOKED"}
ASSIGNMENT_TRANSITIONS = {"CREATED", "SUPERSEDES", "REVOKES"}
ASSIGNMENT_EVENT_ACTIONS = {
    "CREATED": "REVIEW_ASSIGNMENT_CREATED",
    "SUPERSEDES": "REVIEW_ASSIGNMENT_SUPERSEDED",
    "REVOKES": "REVIEW_ASSIGNMENT_REVOKED",
}
ASSIGNMENT_EVENT_ACTION_SET = frozenset(ASSIGNMENT_EVENT_ACTIONS.values())


def _hash_record(value: dict[str, Any], hash_field: str) -> str:
    controlled = {key: item for key, item in value.items() if key != hash_field and not key.startswith("_")}
    return sha256_bytes(canonical_json_bytes(controlled))


def _parse_utc_timestamp(value: object, field_name: str, *, record_id: str | None = None) -> datetime:
    """Parse a timezone-aware RFC 3339 / ISO 8601 timestamp and normalize to UTC.

    Accepts strings only. Trailing ``Z`` is treated as UTC. Naive timestamps and
    non-string values are refused.
    """
    context = f" on record {record_id}" if record_id else ""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid {field_name}{context}: expected a non-empty RFC 3339 / ISO 8601 timestamp string")
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name}{context}: malformed timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"Invalid {field_name}{context}: naive timestamp {value!r} is refused")
    return parsed.astimezone(timezone.utc)


def _review_timestamp() -> str:
    """UTC timestamp with subsecond precision for half-open lineage intervals."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _review_root(workspace: Workspace, case_id: str) -> Path:
    case = workspace.case_path(case_id)
    if not (case / "assessment.json").is_file():
        raise ValueError(f"Unknown case {case_id!r}")
    root = case / "reviews"
    for name in ("assignments", "statements", "dispositions"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def _load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    for item in sorted(path.glob("*.json")):
        value = json.loads(item.read_text(encoding="utf-8"))
        value["_path"] = str(item)
        records.append(value)
    return records


def _target_index(assessment: dict[str, Any]) -> dict[str, set[str]]:
    metadata = assessment.get("assessment_metadata", {})
    return {
        "ASSESSMENT": {str(metadata.get("assessment_id", ""))},
        "FINDING": {str(item.get("requirement_id")) for item in assessment.get("requirement_findings", [])},
        "CLAIM": {str(item.get("claim_id")) for item in assessment.get("claim_register", [])},
        "DECISION": {str(item.get("decision_id")) for item in assessment.get("decision_register", [])},
        "GAP": {str(item.get("gap_id")) for item in assessment.get("gap_register", [])},
    }


def _validate_target(assessment: dict[str, Any], target_type: str, target_id: str) -> None:
    if target_type not in TARGET_TYPES:
        raise ValueError(f"Unsupported target type {target_type!r}")
    ensure_identifier(target_id, "review target ID")
    if target_id not in _target_index(assessment)[target_type]:
        raise ValueError(f"Unknown {target_type.lower()} target {target_id!r}")


def _validate_scope(assessment: dict[str, Any], scope: list[str]) -> list[str]:
    if not scope or not all(isinstance(item, str) and ":" in item for item in scope):
        raise ValueError("Review scope must contain typed entries such as ASSESSMENT:* or FINDING:REQ-ID")
    normalized = sorted(set(scope))
    for item in normalized:
        target_type, target_id = item.split(":", 1)
        if target_type not in TARGET_TYPES:
            raise ValueError(f"Unsupported scope target type {target_type!r}")
        if target_id != "*":
            _validate_target(assessment, target_type, target_id)
    return normalized


def _scope_allows(scope: list[str], target_type: str, target_id: str) -> bool:
    exact = f"{target_type}:{target_id}"
    return "ASSESSMENT:*" in scope or f"{target_type}:*" in scope or exact in scope


def _scope_covers_assignment(authority_scope: list[str], assignment_scope: list[str]) -> bool:
    for item in assignment_scope:
        target_type, target_id = item.split(":", 1)
        if target_id == "*":
            if "ASSESSMENT:*" not in authority_scope and f"{target_type}:*" not in authority_scope:
                return False
        elif not _scope_allows(authority_scope, target_type, target_id):
            return False
    return True


def _assignment_transition(item: dict[str, Any]) -> str:
    return str(item.get("transition") or "CREATED")


def _assignment_index(
    records: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    assignments: dict[str, dict[str, Any]] = {}
    for item in records:
        assignment_id = str(item.get("assignment_id") or "")
        if not assignment_id:
            raise ValueError("Review assignment is missing assignment_id")
        if assignment_id in assignments:
            raise ValueError(f"Duplicate review assignment ID {assignment_id!r}")
        if item.get("assignment_sha256") != _hash_record(item, "assignment_sha256"):
            raise ValueError(f"Review assignment {assignment_id!r} has an invalid hash")
        if item.get("role") not in REVIEW_ROLES:
            raise ValueError(f"Review assignment {assignment_id!r} has an unsupported role")
        if item.get("state") not in ASSIGNMENT_STATES:
            raise ValueError(f"Review assignment {assignment_id!r} has an unsupported state")
        if _assignment_transition(item) not in ASSIGNMENT_TRANSITIONS:
            raise ValueError(f"Review assignment {assignment_id!r} has an unsupported transition")
        assignments[assignment_id] = item

    successors: dict[str, str] = {}
    for assignment_id, item in assignments.items():
        transition = _assignment_transition(item)
        predecessor_id = item.get("predecessor_assignment_id")
        predecessor_hash = item.get("predecessor_assignment_sha256")
        if transition == "CREATED":
            if predecessor_id is not None or predecessor_hash is not None:
                raise ValueError(f"Review assignment {assignment_id!r} has predecessor data on CREATED")
            continue
        if not isinstance(predecessor_id, str) or predecessor_id not in assignments:
            raise ValueError(f"Review assignment {assignment_id!r} has an unresolved predecessor")
        predecessor = assignments[predecessor_id]
        if predecessor.get("state") != "ACTIVE":
            raise ValueError(f"Review assignment {assignment_id!r} follows a non-active predecessor")
        if predecessor_hash != predecessor.get("assignment_sha256"):
            raise ValueError(f"Review assignment {assignment_id!r} has a predecessor hash mismatch")
        if predecessor_id in successors:
            raise ValueError(f"Review assignment {predecessor_id!r} has multiple successor records")
        if not str(item.get("transition_by") or "").strip():
            raise ValueError(f"Review assignment {assignment_id!r} is missing transition attribution")
        if not str(item.get("transition_at") or "").strip():
            raise ValueError(f"Review assignment {assignment_id!r} is missing transition time")
        if not str(item.get("transition_rationale") or "").strip():
            raise ValueError(f"Review assignment {assignment_id!r} is missing transition rationale")
        predecessor_time = _parse_utc_timestamp(
            predecessor.get("assigned_at"),
            "assigned_at",
            record_id=predecessor_id,
        )
        transition_time = _parse_utc_timestamp(
            item.get("transition_at"),
            "transition_at",
            record_id=assignment_id,
        )
        if transition_time < predecessor_time:
            raise ValueError(f"Review assignment {assignment_id!r} predates its predecessor")
        if transition == "SUPERSEDES" and item.get("state") != "ACTIVE":
            raise ValueError(f"Review assignment {assignment_id!r} must be ACTIVE when superseding")
        if transition == "REVOKES":
            if item.get("state") != "REVOKED":
                raise ValueError(f"Review assignment {assignment_id!r} must be REVOKED for a revocation")
            for field in ("reviewer_id", "role", "scope"):
                if item.get(field) != predecessor.get(field):
                    raise ValueError(f"Review assignment {assignment_id!r} changes {field} in a revocation record")
        successors[predecessor_id] = assignment_id

    for origin in assignments:
        visited: set[str] = set()
        current = origin
        while current in successors:
            if current in visited:
                raise ValueError(f"Review assignment lineage cycle detected at {current!r}")
            visited.add(current)
            current = successors[current]
    return assignments, successors


def _effective_assignment_state(
    assignment_id: str,
    assignments: dict[str, dict[str, Any]],
    successors: dict[str, str],
) -> str:
    successor_id = successors.get(assignment_id)
    if successor_id:
        successor = assignments[successor_id]
        return "REVOKED" if _assignment_transition(successor) == "REVOKES" else "SUPERSEDED"
    return str(assignments[assignment_id].get("state"))


def _assignment_was_active_at(
    assignment_id: str,
    timestamp: object,
    assignments: dict[str, dict[str, Any]],
    successors: dict[str, str],
) -> bool:
    """Return whether ``assignment_id`` was effective on the half-open interval.

    Effective iff ``assigned_at <= t < transition_at`` when a successor exists, or
    ``assigned_at <= t`` when the lineage tip is open-ended. At ``t == transition_at``
    the predecessor cannot authorize; the successor tip may.
    """
    assignment = assignments.get(assignment_id)
    if assignment is None or assignment.get("state") != "ACTIVE":
        return False
    try:
        instant = _parse_utc_timestamp(timestamp, "activity_timestamp", record_id=assignment_id)
        assigned_at = _parse_utc_timestamp(
            assignment.get("assigned_at"),
            "assigned_at",
            record_id=assignment_id,
        )
    except ValueError:
        return False
    if instant < assigned_at:
        return False
    successor_id = successors.get(assignment_id)
    if not successor_id:
        return True
    try:
        transition_at = _parse_utc_timestamp(
            assignments[successor_id].get("transition_at"),
            "transition_at",
            record_id=successor_id,
        )
    except ValueError:
        return False
    return instant < transition_at


def _collect_independent_assignment_errors(item: dict[str, Any]) -> list[str]:
    """Collect per-record defects without trusting lineage reconstruction."""
    assignment_id = str(item.get("assignment_id") or "?")
    errors: list[str] = []
    if item.get("assignment_sha256") != _hash_record(item, "assignment_sha256"):
        errors.append(f"assignment {assignment_id}: hash mismatch")
    if item.get("role") not in REVIEW_ROLES:
        errors.append(f"assignment {assignment_id}: unsupported role")
    if item.get("state") not in ASSIGNMENT_STATES:
        errors.append(f"assignment {assignment_id}: unsupported state")
    transition = _assignment_transition(item)
    if transition not in ASSIGNMENT_TRANSITIONS:
        errors.append(f"assignment {assignment_id}: unsupported transition")
    for field in ("assigned_at", "transition_at"):
        value = item.get(field)
        if value is None and field == "transition_at" and transition == "CREATED":
            continue
        if value is None and field == "assigned_at":
            errors.append(f"assignment {assignment_id}: missing {field}")
            continue
        if value is None:
            continue
        try:
            _parse_utc_timestamp(value, field, record_id=assignment_id)
        except ValueError as exc:
            errors.append(f"assignment {assignment_id}: {exc}")
    return errors


def _verify_assignment_event_correspondence(
    assignments: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
) -> list[str]:
    """Require exactly one matching transition event per assignment; never silent-repair."""
    errors: list[str] = []
    transition_events = [event for event in events if event.get("action") in ASSIGNMENT_EVENT_ACTION_SET]
    matched_indices: set[int] = set()

    for assignment_id, item in assignments.items():
        transition = _assignment_transition(item)
        expected_action = ASSIGNMENT_EVENT_ACTIONS.get(transition)
        if expected_action is None:
            continue
        matches = [
            (index, event)
            for index, event in enumerate(transition_events)
            if (event.get("payload") or {}).get("assignment_id") == assignment_id
        ]
        if not matches:
            errors.append(f"assignment {assignment_id}: missing matching {expected_action} event")
            continue
        if len(matches) > 1:
            errors.append(f"assignment {assignment_id}: duplicate assignment transition events")
            matched_indices.update(index for index, _event in matches)
            continue

        index, event = matches[0]
        matched_indices.add(index)
        payload = event.get("payload") or {}
        expected_actor = item.get("transition_by") or item.get("assigned_by")
        checks = [
            (event.get("action") == expected_action, "event action mismatch"),
            (payload.get("assignment_sha256") == item.get("assignment_sha256"), "event assignment digest mismatch"),
            (event.get("actor") == expected_actor, "event actor mismatch"),
            (payload.get("transition") == transition, "event transition mismatch"),
            (payload.get("reviewer_id") == item.get("reviewer_id"), "event reviewer mismatch"),
            (payload.get("role") == item.get("role"), "event role mismatch"),
        ]
        for ok, message in checks:
            if not ok:
                errors.append(f"assignment {assignment_id}: {message}")
        if transition in {"SUPERSEDES", "REVOKES"}:
            if payload.get("predecessor_assignment_id") != item.get("predecessor_assignment_id"):
                errors.append(f"assignment {assignment_id}: event predecessor id mismatch")
            if payload.get("predecessor_assignment_sha256") != item.get("predecessor_assignment_sha256"):
                errors.append(f"assignment {assignment_id}: event predecessor digest mismatch")

    for index, event in enumerate(transition_events):
        if index in matched_indices:
            continue
        payload = event.get("payload") or {}
        orphan_id = payload.get("assignment_id") or "?"
        errors.append(f"assignment event {orphan_id}: orphan transition event without matching record")
    return errors


def _active_assignments(workspace: Workspace, case_id: str, reviewer_id: str) -> list[dict[str, Any]]:
    root = _review_root(workspace, case_id)
    assignments, successors = _assignment_index(_load_records(root / "assignments"))
    return [
        item
        for assignment_id, item in assignments.items()
        if item.get("reviewer_id") == reviewer_id and item.get("state") == "ACTIVE" and assignment_id not in successors
    ]


def _assignment_transition_authorized(
    workspace: Workspace,
    case_id: str,
    assignment: dict[str, Any],
    actor: str,
    *,
    allow_reviewer_relinquishment: bool,
) -> bool:
    if actor == assignment.get("assigned_by"):
        return True
    if allow_reviewer_relinquishment and actor == assignment.get("reviewer_id"):
        return True
    return any(
        item.get("role") in DECISION_ROLES
        and _scope_covers_assignment(item.get("scope", []), assignment.get("scope", []))
        for item in _active_assignments(workspace, case_id, actor)
    )


def _assignment_record(
    workspace: Workspace,
    case_id: str,
    reviewer_id: str,
    role: str,
    scope: list[str],
    *,
    actor: str,
    state: str,
    transition: str,
    predecessor: dict[str, Any] | None = None,
    rationale: str | None = None,
) -> dict[str, Any]:
    recorded_at = _review_timestamp()
    predecessor_id = predecessor.get("assignment_id") if predecessor else None
    predecessor_hash = predecessor.get("assignment_sha256") if predecessor else None
    seed = canonical_json_bytes(
        {
            "case_id": case_id,
            "reviewer_id": reviewer_id,
            "role": role,
            "scope": scope,
            "actor": actor,
            "state": state,
            "transition": transition,
            "predecessor_assignment_id": predecessor_id,
            "predecessor_assignment_sha256": predecessor_hash,
            "rationale": rationale,
            "assessment_sha256": sha256_file(workspace.case_path(case_id) / "assessment.json"),
            "recorded_at": recorded_at,
        }
    )
    assignment_id = f"RA-{recorded_at.replace(':', '').replace('-', '')}-{sha256_bytes(seed)[:12]}"
    if transition == "REVOKES" and predecessor is not None:
        assigned_by = predecessor.get("assigned_by")
        assigned_at = predecessor.get("assigned_at")
    else:
        assigned_by = actor
        assigned_at = recorded_at
    record = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "assignment_id": assignment_id,
        "case_id": case_id,
        "reviewer_id": reviewer_id,
        "role": role,
        "scope": scope,
        "state": state,
        "assigned_by": assigned_by,
        "assigned_at": assigned_at,
        "assessment_sha256": sha256_file(workspace.case_path(case_id) / "assessment.json"),
        "transition": transition,
        "predecessor_assignment_id": predecessor_id,
        "predecessor_assignment_sha256": predecessor_hash,
        "transition_by": actor,
        "transition_at": recorded_at,
        "transition_rationale": rationale or "Initial assignment",
        "authority_profile": "LOCAL_UNAUTHENTICATED_ATTRIBUTION",
        "identity_boundary": (
            "The workbench records a claimed local identity and role; it does not authenticate a person or institution."
        ),
        "assessment_mutation": "NONE_PERFORMED_BY_ASSIGNMENT_TRANSITION",
    }
    record["assignment_sha256"] = _hash_record(record, "assignment_sha256")
    return record


def _write_assignment(
    workspace: Workspace,
    case_id: str,
    record: dict[str, Any],
    *,
    actor: str,
    event_action: str,
    event_payload: dict[str, Any],
) -> dict[str, Any]:
    root = _review_root(workspace, case_id)
    output = root / "assignments" / f"{record['assignment_id']}.json"
    if output.exists():
        raise ValueError(f"An identical review assignment already exists for this timestamp: {record['assignment_id']}")
    atomic_write_json(output, record)
    append_event(
        workspace.case_path(case_id) / "events.jsonl",
        event_action,
        actor,
        {**event_payload, "assignment_sha256": record["assignment_sha256"]},
    )
    return {"assignment": record, "path": str(output)}


def create_review_assignment(
    workspace: Workspace,
    case_id: str,
    reviewer_id: str,
    role: str,
    scope: list[str],
    *,
    actor: str = "local-user",
) -> dict[str, Any]:
    ensure_identifier(reviewer_id, "reviewer ID")
    ensure_identifier(actor, "actor ID")
    if role not in REVIEW_ROLES:
        raise ValueError(f"Unsupported review role {role!r}")
    if role in DECISION_ROLES and actor == reviewer_id:
        raise ValueError(
            f"Self-assignment is refused for decision role {role!r}; "
            "a distinct assigning actor is required under LOCAL_UNAUTHENTICATED_ATTRIBUTION."
        )
    case = workspace.case_path(case_id)
    with case_mutation_lock(case):
        assessment = workspace.load_case(case_id)
        normalized_scope = _validate_scope(assessment, scope)
        root = _review_root(workspace, case_id)
        _assignment_index(_load_records(root / "assignments"))
        record = _assignment_record(
            workspace,
            case_id,
            reviewer_id,
            role,
            normalized_scope,
            actor=actor,
            state="ACTIVE",
            transition="CREATED",
        )
        return _write_assignment(
            workspace,
            case_id,
            record,
            actor=actor,
            event_action="REVIEW_ASSIGNMENT_CREATED",
            event_payload={
                "assignment_id": record["assignment_id"],
                "reviewer_id": reviewer_id,
                "role": role,
                "transition": "CREATED",
            },
        )


def revoke_review_assignment(
    workspace: Workspace,
    case_id: str,
    assignment_id: str,
    rationale: str,
    *,
    actor: str,
) -> dict[str, Any]:
    ensure_identifier(assignment_id, "assignment ID")
    ensure_identifier(actor, "actor ID")
    rationale = rationale.strip()
    if not rationale:
        raise ValueError("Assignment revocation rationale must not be empty")
    case = workspace.case_path(case_id)
    with case_mutation_lock(case):
        root = _review_root(workspace, case_id)
        assignments, successors = _assignment_index(_load_records(root / "assignments"))
        assignment = assignments.get(assignment_id)
        if assignment is None:
            raise FileNotFoundError(f"Unknown review assignment {assignment_id}")
        if assignment.get("state") != "ACTIVE" or assignment_id in successors:
            raise ValueError(f"Review assignment {assignment_id!r} is not an active lineage tip")
        if not _assignment_transition_authorized(
            workspace,
            case_id,
            assignment,
            actor,
            allow_reviewer_relinquishment=True,
        ):
            raise ValueError(f"Actor {actor!r} is not authorized to revoke assignment {assignment_id!r}")
        record = _assignment_record(
            workspace,
            case_id,
            str(assignment["reviewer_id"]),
            str(assignment["role"]),
            list(assignment.get("scope", [])),
            actor=actor,
            state="REVOKED",
            transition="REVOKES",
            predecessor=assignment,
            rationale=rationale,
        )
        return _write_assignment(
            workspace,
            case_id,
            record,
            actor=actor,
            event_action="REVIEW_ASSIGNMENT_REVOKED",
            event_payload={
                "assignment_id": record["assignment_id"],
                "predecessor_assignment_id": assignment_id,
                "predecessor_assignment_sha256": assignment["assignment_sha256"],
                "reviewer_id": assignment["reviewer_id"],
                "role": assignment["role"],
                "transition": "REVOKES",
            },
        )


def supersede_review_assignment(
    workspace: Workspace,
    case_id: str,
    assignment_id: str,
    reviewer_id: str,
    role: str,
    scope: list[str],
    rationale: str,
    *,
    actor: str,
) -> dict[str, Any]:
    ensure_identifier(assignment_id, "assignment ID")
    ensure_identifier(reviewer_id, "reviewer ID")
    ensure_identifier(actor, "actor ID")
    rationale = rationale.strip()
    if not rationale:
        raise ValueError("Assignment supersession rationale must not be empty")
    if role not in REVIEW_ROLES:
        raise ValueError(f"Unsupported review role {role!r}")
    if role in DECISION_ROLES and actor == reviewer_id:
        raise ValueError(
            f"Self-assignment is refused for decision role {role!r}; "
            "a distinct assigning actor is required under LOCAL_UNAUTHENTICATED_ATTRIBUTION."
        )
    case = workspace.case_path(case_id)
    with case_mutation_lock(case):
        assessment = workspace.load_case(case_id)
        normalized_scope = _validate_scope(assessment, scope)
        root = _review_root(workspace, case_id)
        assignments, successors = _assignment_index(_load_records(root / "assignments"))
        assignment = assignments.get(assignment_id)
        if assignment is None:
            raise FileNotFoundError(f"Unknown review assignment {assignment_id}")
        if assignment.get("state") != "ACTIVE" or assignment_id in successors:
            raise ValueError(f"Review assignment {assignment_id!r} is not an active lineage tip")
        if not _assignment_transition_authorized(
            workspace,
            case_id,
            assignment,
            actor,
            allow_reviewer_relinquishment=False,
        ):
            raise ValueError(f"Actor {actor!r} is not authorized to supersede assignment {assignment_id!r}")
        record = _assignment_record(
            workspace,
            case_id,
            reviewer_id,
            role,
            normalized_scope,
            actor=actor,
            state="ACTIVE",
            transition="SUPERSEDES",
            predecessor=assignment,
            rationale=rationale,
        )
        return _write_assignment(
            workspace,
            case_id,
            record,
            actor=actor,
            event_action="REVIEW_ASSIGNMENT_SUPERSEDED",
            event_payload={
                "assignment_id": record["assignment_id"],
                "predecessor_assignment_id": assignment_id,
                "predecessor_assignment_sha256": assignment["assignment_sha256"],
                "reviewer_id": reviewer_id,
                "role": role,
                "transition": "SUPERSEDES",
            },
        )


def submit_review_statement(
    workspace: Workspace,
    case_id: str,
    reviewer_id: str,
    target_type: str,
    target_id: str,
    position: str,
    rationale: str,
    *,
    evidence_ids: list[str] | None = None,
    conditions: list[str] | None = None,
    proposed_change: str | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    ensure_identifier(reviewer_id, "reviewer ID")
    if position not in POSITIONS:
        raise ValueError(f"Unsupported review position {position!r}")
    rationale = rationale.strip()
    if not rationale:
        raise ValueError("Review rationale must not be empty")
    actor = actor or reviewer_id
    if actor != reviewer_id:
        raise ValueError("The recorded actor must match reviewer_id in the local reference workflow")

    case = workspace.case_path(case_id)
    with case_mutation_lock(case):
        assessment = workspace.load_case(case_id)
        _validate_target(assessment, target_type, target_id)
        assignments = _active_assignments(workspace, case_id, reviewer_id)
        if not any(_scope_allows(item.get("scope", []), target_type, target_id) for item in assignments):
            raise ValueError(f"Reviewer {reviewer_id!r} has no active assignment covering {target_type}:{target_id}")

        known_evidence = {str(item.get("evidence_id")) for item in assessment.get("evidence_register", [])}
        refs = sorted(set(evidence_ids or []))
        unknown = sorted(set(refs) - known_evidence)
        if unknown:
            raise ValueError(f"Unknown evidence IDs: {', '.join(unknown)}")

        assessment_path = workspace.case_path(case_id) / "assessment.json"
        submitted_at = _review_timestamp()
        seed = canonical_json_bytes(
            {
                "case_id": case_id,
                "reviewer_id": reviewer_id,
                "target_type": target_type,
                "target_id": target_id,
                "position": position,
                "rationale": rationale,
                "assessment_sha256": sha256_file(assessment_path),
                "submitted_at": submitted_at,
            }
        )
        statement_id = f"RS-{submitted_at.replace(':', '').replace('-', '')}-{sha256_bytes(seed)[:12]}"
        record = {
            "schema_version": REVIEW_SCHEMA_VERSION,
            "statement_id": statement_id,
            "case_id": case_id,
            "reviewer_id": reviewer_id,
            "assignment_ids": sorted(item["assignment_id"] for item in assignments),
            "target_type": target_type,
            "target_id": target_id,
            "position": position,
            "rationale": rationale,
            "evidence_ids": refs,
            "conditions": conditions or [],
            "proposed_change": proposed_change,
            "assessment_sha256": sha256_file(assessment_path),
            "submitted_at": submitted_at,
            "actor": actor,
            "assessment_mutation": "NONE_PERFORMED_BY_REVIEW_STATEMENT",
        }
        record["statement_sha256"] = _hash_record(record, "statement_sha256")
        root = _review_root(workspace, case_id)
        output = root / "statements" / f"{statement_id}.json"
        if output.exists():
            raise ValueError(f"An identical review statement already exists for this timestamp: {statement_id}")
        atomic_write_json(output, record)
        append_event(
            workspace.case_path(case_id) / "events.jsonl",
            "REVIEW_STATEMENT_SUBMITTED",
            actor,
            {
                "statement_id": statement_id,
                "target": f"{target_type}:{target_id}",
                "position": position,
                "statement_sha256": record["statement_sha256"],
            },
        )
        return {"statement": record, "path": str(output)}


def dispose_review_statement(
    workspace: Workspace,
    case_id: str,
    statement_id: str,
    disposition: str,
    rationale: str,
    *,
    actor: str,
) -> dict[str, Any]:
    ensure_identifier(statement_id, "statement ID")
    ensure_identifier(actor, "actor ID")
    if disposition not in DISPOSITIONS:
        raise ValueError(f"Unsupported review disposition {disposition!r}")
    rationale = rationale.strip()
    if not rationale:
        raise ValueError("Disposition rationale must not be empty")

    case = workspace.case_path(case_id)
    with case_mutation_lock(case):
        root = _review_root(workspace, case_id)
        statement_path = root / "statements" / f"{statement_id}.json"
        if not statement_path.is_file():
            raise FileNotFoundError(f"Unknown review statement {statement_id}")
        statement = json.loads(statement_path.read_text(encoding="utf-8"))
        if statement.get("statement_sha256") != _hash_record(statement, "statement_sha256"):
            raise ValueError("Review statement hash is invalid")
        current_assessment_sha256 = sha256_file(workspace.case_path(case_id) / "assessment.json")
        if statement.get("assessment_sha256") != current_assessment_sha256:
            raise ValueError(
                "Review statement is stale: assessment_sha256 no longer matches the current assessment. "
                "Submit a successor statement or reaffirmation against the current assessment before disposition."
            )
        output = root / "dispositions" / f"{statement_id}.json"
        if output.exists():
            raise ValueError(f"A disposition is already recorded for {statement_id}")

        assignments = _active_assignments(workspace, case_id, actor)
        target_type = str(statement.get("target_type"))
        target_id = str(statement.get("target_id"))
        authorized = any(
            item.get("role") in DECISION_ROLES and _scope_allows(item.get("scope", []), target_type, target_id)
            for item in assignments
        )
        if not authorized:
            raise ValueError(f"Actor {actor!r} has no active decision role covering {target_type}:{target_id}")

        record = {
            "schema_version": REVIEW_SCHEMA_VERSION,
            "statement_id": statement_id,
            "statement_sha256": statement["statement_sha256"],
            "disposition": disposition,
            "rationale": rationale,
            "actor": actor,
            "assignment_ids": sorted(item["assignment_id"] for item in assignments),
            "recorded_at": _review_timestamp(),
            "assessment_mutation": "NONE_PERFORMED_BY_DISPOSITION_RECORD",
            "authority_profile": "LOCAL_UNAUTHENTICATED_ATTRIBUTION",
            "authority_boundary": (
                "This record attributes a local workflow decision; it does not establish legal or institutional authority."
            ),
        }
        record["disposition_sha256"] = _hash_record(record, "disposition_sha256")
        atomic_write_json(output, record)
        append_event(
            workspace.case_path(case_id) / "events.jsonl",
            "REVIEW_STATEMENT_DISPOSED",
            actor,
            {
                "statement_id": statement_id,
                "disposition": disposition,
                "disposition_sha256": record["disposition_sha256"],
            },
        )
        return {"disposition": record, "path": str(output)}


def load_review_records(workspace: Workspace, case_id: str) -> dict[str, list[dict[str, Any]]]:
    root = _review_root(workspace, case_id)
    return {
        "assignments": _load_records(root / "assignments"),
        "statements": _load_records(root / "statements"),
        "dispositions": _load_records(root / "dispositions"),
    }


def verify_review_records(workspace: Workspace, case_id: str) -> dict[str, Any]:
    records = load_review_records(workspace, case_id)
    assessment = workspace.load_case(case_id)
    assessment_sha256 = sha256_file(workspace.case_path(case_id) / "assessment.json")
    targets = _target_index(assessment)
    evidence_ids = {str(item.get("evidence_id")) for item in assessment.get("evidence_register", [])}
    errors: list[str] = []
    warnings: list[str] = []
    lineage_trusted = True

    try:
        assignments, successors = _assignment_index(records["assignments"])
    except ValueError as exc:
        lineage_trusted = False
        assignments = {
            str(item.get("assignment_id")): item
            for item in records["assignments"]
            if item.get("assignment_id") is not None
        }
        successors = {}
        errors.append(str(exc))
        for item in records["assignments"]:
            errors.extend(_collect_independent_assignment_errors(item))

    for assignment_id, item in assignments.items():
        for scope_item in item.get("scope", []):
            if not isinstance(scope_item, str) or ":" not in scope_item:
                errors.append(f"assignment {assignment_id}: invalid scope entry")
                continue
            target_type, target_id = scope_item.split(":", 1)
            if target_type not in TARGET_TYPES:
                errors.append(f"assignment {assignment_id}: unsupported scope target type")
            elif target_id != "*" and target_id not in targets.get(target_type, set()):
                errors.append(f"assignment {assignment_id}: unresolved scope target")

    statements = {str(item.get("statement_id")): item for item in records["statements"]}
    for statement_id, item in statements.items():
        if item.get("statement_sha256") != _hash_record(item, "statement_sha256"):
            errors.append(f"statement {statement_id}: hash mismatch")
        target_type = str(item.get("target_type"))
        target_id = str(item.get("target_id"))
        if target_type not in targets or target_id not in targets.get(target_type, set()):
            errors.append(f"statement {statement_id}: unresolved target")
        if item.get("position") not in POSITIONS:
            errors.append(f"statement {statement_id}: unsupported position")
        if item.get("actor") != item.get("reviewer_id"):
            errors.append(f"statement {statement_id}: actor does not match reviewer")
        if item.get("assessment_sha256") != assessment_sha256:
            warnings.append(f"statement {statement_id}: assessment has changed since submission")
        unknown = sorted(set(item.get("evidence_ids", [])) - evidence_ids)
        if unknown:
            errors.append(f"statement {statement_id}: unknown evidence IDs {', '.join(unknown)}")
        submitted_at = item.get("submitted_at")
        linked = [assignments.get(str(value)) for value in item.get("assignment_ids", [])]
        covering = lineage_trusted and any(
            record is not None
            and record.get("reviewer_id") == item.get("reviewer_id")
            and _scope_allows(record.get("scope", []), target_type, target_id)
            and _assignment_was_active_at(str(record.get("assignment_id")), submitted_at, assignments, successors)
            for record in linked
        )
        if not covering:
            errors.append(f"statement {statement_id}: no valid covering assignment at submission time")

    seen_dispositions: set[str] = set()
    for item in records["dispositions"]:
        statement_id = str(item.get("statement_id"))
        if statement_id in seen_dispositions:
            errors.append(f"statement {statement_id}: duplicate disposition")
        seen_dispositions.add(statement_id)
        if item.get("disposition_sha256") != _hash_record(item, "disposition_sha256"):
            errors.append(f"disposition {statement_id}: hash mismatch")
        statement = statements.get(statement_id)
        if statement is None:
            errors.append(f"disposition {statement_id}: statement missing")
        elif item.get("statement_sha256") != statement.get("statement_sha256"):
            errors.append(f"disposition {statement_id}: statement hash mismatch")
        if item.get("disposition") not in DISPOSITIONS:
            errors.append(f"disposition {statement_id}: unsupported disposition")
        linked = [assignments.get(str(value)) for value in item.get("assignment_ids", [])]
        target_type = str(statement.get("target_type")) if statement else ""
        target_id = str(statement.get("target_id")) if statement else ""
        recorded_at = item.get("recorded_at")
        covering = lineage_trusted and any(
            record is not None
            and record.get("reviewer_id") == item.get("actor")
            and record.get("role") in DECISION_ROLES
            and _scope_allows(record.get("scope", []), target_type, target_id)
            and _assignment_was_active_at(str(record.get("assignment_id")), recorded_at, assignments, successors)
            for record in linked
        )
        if not covering:
            errors.append(f"disposition {statement_id}: no valid covering decision assignment at disposition time")

    event_report = verify_chain(workspace.case_path(case_id) / "events.jsonl")
    if not event_report["valid"]:
        errors.extend(f"event chain: {error}" for error in event_report["errors"])
    else:
        try:
            events = load_events(workspace.case_path(case_id) / "events.jsonl")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"event chain: unable to load events for assignment correspondence ({exc})")
        else:
            errors.extend(_verify_assignment_event_correspondence(assignments, events))

    open_statement_count = sum(statement_id not in seen_dispositions for statement_id in statements)
    stale_statement_count = sum(item.get("assessment_sha256") != assessment_sha256 for item in records["statements"])
    active_assignment_count = (
        0
        if not lineage_trusted
        else sum(
            item.get("state") == "ACTIVE" and assignment_id not in successors
            for assignment_id, item in assignments.items()
        )
    )
    return {
        "valid": not errors,
        "case_id": case_id,
        "counts": {
            "assignments": len(records["assignments"]),
            "statements": len(records["statements"]),
            "dispositions": len(records["dispositions"]),
            "open_statements": open_statement_count,
            "disagreements": sum(item.get("position") == "DISAGREE" for item in records["statements"]),
            "stale_statements": stale_statement_count,
        },
        "assignment_summary": {
            "active": active_assignment_count,
            "supersessions": sum(_assignment_transition(item) == "SUPERSEDES" for item in assignments.values()),
            "revocations": sum(_assignment_transition(item) == "REVOKES" for item in assignments.values()),
            "records": len(assignments),
        },
        "errors": errors,
        "warnings": warnings,
        "event_chain_valid": event_report["valid"],
        "boundary": (
            "Review-record integrity and role linkage do not authenticate identities "
            "or establish institutional decision authority."
        ),
    }


def render_review_markdown(workspace: Workspace, case_id: str) -> str:
    records = load_review_records(workspace, case_id)
    verification = verify_review_records(workspace, case_id)
    lineage_trusted = True
    try:
        assignments, successors = _assignment_index(records["assignments"])
    except ValueError:
        lineage_trusted = False
        assignments = {
            str(item.get("assignment_id")): item
            for item in records["assignments"]
            if item.get("assignment_id") is not None
        }
        successors = {}
    dispositions = {item.get("statement_id"): item for item in records["dispositions"]}
    lines = [
        f"# Review record: {case_id}",
        "",
        (
            "> This report attributes local workflow records. It does not authenticate reviewers "
            "or create scientific, legal, clinical, or institutional authority."
        ),
        "",
        "## State",
        "",
        f"- Integrity: `{'VALID' if verification['valid'] else 'INVALID'}`",
        f"- Assignment records: {verification['counts']['assignments']}",
        f"- Effective active assignments: {verification['assignment_summary']['active']}",
        f"- Assignment supersessions: {verification['assignment_summary']['supersessions']}",
        f"- Assignment revocations: {verification['assignment_summary']['revocations']}",
        f"- Statements: {verification['counts']['statements']}",
        f"- Disagreements: {verification['counts']['disagreements']}",
        f"- Open statements: {verification['counts']['open_statements']}",
        f"- Statements tied to an earlier assessment hash: {verification['counts']['stale_statements']}",
        "",
        "## Assignment lineage",
        "",
        "| Assignment | Reviewer | Role | Scope | Recorded state | Effective state | Transition | Predecessor |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in records["assignments"]:
        assignment_id = str(item.get("assignment_id"))
        if not lineage_trusted or assignment_id not in assignments:
            effective_state = "INVALID"
        else:
            effective_state = _effective_assignment_state(assignment_id, assignments, successors)
        lines.append(
            f"| {assignment_id} | {item.get('reviewer_id')} | {item.get('role')} | "
            f"{', '.join(item.get('scope', []))} | {item.get('state')} | {effective_state} | "
            f"{_assignment_transition(item)} | {item.get('predecessor_assignment_id') or '—'} |"
        )
    lines.extend(
        [
            "",
            "## Statements and dispositions",
            "",
            "| Statement | Reviewer | Target | Position | Rationale | Disposition | Disposition rationale |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for item in records["statements"]:
        disposition = dispositions.get(item.get("statement_id"), {})
        rationale = str(item.get("rationale", "")).replace("|", "\\|").replace("\n", " ")
        disposition_rationale = str(disposition.get("rationale", "")).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {item.get('statement_id')} | {item.get('reviewer_id')} | "
            f"{item.get('target_type')}:{item.get('target_id')} | {item.get('position')} | {rationale} | "
            f"{disposition.get('disposition', 'OPEN')} | {disposition_rationale} |"
        )
    if verification["errors"]:
        lines.extend(["", "## Integrity errors", ""])
        lines.extend(f"- {error}" for error in verification["errors"])
    if verification["warnings"]:
        lines.extend(["", "## Review-state warnings", ""])
        lines.extend(f"- {warning}" for warning in verification["warnings"])
    return "\n".join(lines) + "\n"
