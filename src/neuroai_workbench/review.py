from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .events import append_event, verify_chain
from .util import atomic_write_json, canonical_json_bytes, ensure_identifier, sha256_bytes, sha256_file, utc_now
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


def _hash_record(value: dict[str, Any], hash_field: str) -> str:
    controlled = {key: item for key, item in value.items() if key != hash_field and not key.startswith("_")}
    return sha256_bytes(canonical_json_bytes(controlled))


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


def _scope_allows(scope: list[str], target_type: str, target_id: str) -> bool:
    exact = f"{target_type}:{target_id}"
    return "ASSESSMENT:*" in scope or f"{target_type}:*" in scope or exact in scope


def _active_assignments(workspace: Workspace, case_id: str, reviewer_id: str) -> list[dict[str, Any]]:
    root = _review_root(workspace, case_id)
    active: list[dict[str, Any]] = []
    for item in _load_records(root / "assignments"):
        assignment_id = str(item.get("assignment_id"))
        if item.get("assignment_sha256") != _hash_record(item, "assignment_sha256"):
            raise ValueError(f"Review assignment {assignment_id!r} has an invalid hash")
        if item.get("role") not in REVIEW_ROLES:
            raise ValueError(f"Review assignment {assignment_id!r} has an unsupported role")
        if item.get("reviewer_id") == reviewer_id and item.get("state") == "ACTIVE":
            active.append(item)
    return active


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
    if not scope or not all(isinstance(item, str) and ":" in item for item in scope):
        raise ValueError("Review scope must contain typed entries such as ASSESSMENT:* or FINDING:REQ-ID")

    assessment = workspace.load_case(case_id)
    for item in scope:
        target_type, target_id = item.split(":", 1)
        if target_type not in TARGET_TYPES:
            raise ValueError(f"Unsupported scope target type {target_type!r}")
        if target_id != "*":
            _validate_target(assessment, target_type, target_id)

    seed = canonical_json_bytes(
        {
            "case_id": case_id,
            "reviewer_id": reviewer_id,
            "role": role,
            "scope": sorted(set(scope)),
            "actor": actor,
            "assessment_sha256": sha256_file(workspace.case_path(case_id) / "assessment.json"),
        }
    )
    assignment_id = f"RA-{utc_now().replace(':', '').replace('-', '')}-{sha256_bytes(seed)[:12]}"
    record = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "assignment_id": assignment_id,
        "case_id": case_id,
        "reviewer_id": reviewer_id,
        "role": role,
        "scope": sorted(set(scope)),
        "state": "ACTIVE",
        "assigned_by": actor,
        "assigned_at": utc_now(),
        "assessment_sha256": sha256_file(workspace.case_path(case_id) / "assessment.json"),
        "authority_profile": "LOCAL_UNAUTHENTICATED_ATTRIBUTION",
        "identity_boundary": (
            "The workbench records a claimed local identity and role; it does not authenticate a person or institution."
        ),
    }
    record["assignment_sha256"] = _hash_record(record, "assignment_sha256")
    root = _review_root(workspace, case_id)
    output = root / "assignments" / f"{assignment_id}.json"
    if output.exists():
        raise ValueError(f"An identical review assignment already exists for this timestamp: {assignment_id}")
    atomic_write_json(output, record)
    append_event(
        workspace.case_path(case_id) / "events.jsonl",
        "REVIEW_ASSIGNMENT_CREATED",
        actor,
        {
            "assignment_id": assignment_id,
            "reviewer_id": reviewer_id,
            "role": role,
            "assignment_sha256": record["assignment_sha256"],
        },
    )
    return {"assignment": record, "path": str(output)}


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
    seed = canonical_json_bytes(
        {
            "case_id": case_id,
            "reviewer_id": reviewer_id,
            "target_type": target_type,
            "target_id": target_id,
            "position": position,
            "rationale": rationale,
            "assessment_sha256": sha256_file(assessment_path),
        }
    )
    statement_id = f"RS-{utc_now().replace(':', '').replace('-', '')}-{sha256_bytes(seed)[:12]}"
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
        "submitted_at": utc_now(),
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
        "recorded_at": utc_now(),
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
    assignments = {str(item.get("assignment_id")): item for item in records["assignments"]}
    statements = {str(item.get("statement_id")): item for item in records["statements"]}
    errors: list[str] = []
    warnings: list[str] = []

    for assignment_id, item in assignments.items():
        if item.get("assignment_sha256") != _hash_record(item, "assignment_sha256"):
            errors.append(f"assignment {assignment_id}: hash mismatch")
        if item.get("role") not in REVIEW_ROLES:
            errors.append(f"assignment {assignment_id}: unsupported role")
        if item.get("state") != "ACTIVE":
            errors.append(f"assignment {assignment_id}: unsupported state")
        for scope_item in item.get("scope", []):
            if not isinstance(scope_item, str) or ":" not in scope_item:
                errors.append(f"assignment {assignment_id}: invalid scope entry")
                continue
            target_type, target_id = scope_item.split(":", 1)
            if target_type not in TARGET_TYPES:
                errors.append(f"assignment {assignment_id}: unsupported scope target type")
            elif target_id != "*" and target_id not in targets.get(target_type, set()):
                errors.append(f"assignment {assignment_id}: unresolved scope target")

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
        linked = [assignments.get(str(value)) for value in item.get("assignment_ids", [])]
        if not linked or not any(
            record is not None
            and record.get("reviewer_id") == item.get("reviewer_id")
            and _scope_allows(record.get("scope", []), target_type, target_id)
            for record in linked
        ):
            errors.append(f"statement {statement_id}: no valid covering assignment")

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
        if not any(
            record is not None
            and record.get("reviewer_id") == item.get("actor")
            and record.get("role") in DECISION_ROLES
            and _scope_allows(record.get("scope", []), target_type, target_id)
            for record in linked
        ):
            errors.append(f"disposition {statement_id}: no valid covering decision assignment")

    event_report = verify_chain(workspace.case_path(case_id) / "events.jsonl")
    if not event_report["valid"]:
        errors.extend(f"event chain: {error}" for error in event_report["errors"])
    open_statement_count = sum(statement_id not in seen_dispositions for statement_id in statements)
    stale_statement_count = sum(item.get("assessment_sha256") != assessment_sha256 for item in records["statements"])
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
        f"- Assignments: {verification['counts']['assignments']}",
        f"- Statements: {verification['counts']['statements']}",
        f"- Disagreements: {verification['counts']['disagreements']}",
        f"- Open statements: {verification['counts']['open_statements']}",
        f"- Statements tied to an earlier assessment hash: {verification['counts']['stale_statements']}",
        "",
        "## Assignments",
        "",
        "| Assignment | Reviewer | Role | Scope | State |",
        "|---|---|---|---|---|",
    ]
    for item in records["assignments"]:
        lines.append(
            f"| {item.get('assignment_id')} | {item.get('reviewer_id')} | {item.get('role')} | "
            f"{', '.join(item.get('scope', []))} | {item.get('state')} |"
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
