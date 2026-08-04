from __future__ import annotations

import json
from typing import Any

from .assessment_paths import apply_field_patches, get_at_path, normalize_target_path, path_within_review_target
from .events import load_events, verify_chain
from .util import canonical_json_bytes, ensure_identifier, sha256_bytes, sha256_file
from .workspace import Workspace


def assessment_edit_authority_assignments(
    workspace: Workspace,
    case_id: str,
    actor: str,
    targets: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Return active, event-linked local decision assignments covering every target."""
    from .review import (
        DECISION_ROLES,
        _assignment_index,
        _load_records,
        _review_root,
        _scope_allows,
        _verify_assignment_event_correspondence,
    )

    ensure_identifier(actor, "actor ID")
    if not targets:
        raise ValueError("At least one assessment-edit authority target is required")
    event_path = workspace.case_path(case_id) / "events.jsonl"
    chain = verify_chain(event_path)
    if not chain.get("valid") or not chain.get("trailer_valid"):
        raise ValueError("Event chain is invalid; assessment-edit authority is refused")
    root = _review_root(workspace, case_id)
    assignments, successors = _assignment_index(_load_records(root / "assignments"))
    correspondence_errors = _verify_assignment_event_correspondence(assignments, load_events(event_path))
    if correspondence_errors:
        raise ValueError("Review assignment event correspondence failed: " + "; ".join(correspondence_errors))
    active = [
        item
        for assignment_id, item in assignments.items()
        if item.get("reviewer_id") == actor
        and item.get("role") in DECISION_ROLES
        and item.get("state") == "ACTIVE"
        and assignment_id not in successors
    ]
    used: dict[str, dict[str, Any]] = {}
    for target_type, target_id in targets:
        covering = [item for item in active if _scope_allows(item.get("scope", []), target_type, target_id)]
        if not covering:
            raise ValueError(
                f"Actor {actor!r} has no active assessment-edit decision role covering "
                f"{target_type}:{target_id}"
            )
        for item in covering:
            used[str(item["assignment_id"])] = item
    return [used[key] for key in sorted(used)]


def apply_review_proposal(
    workspace: Workspace,
    case_id: str,
    statement_id: str,
    *,
    actor: str,
    expected_assessment_sha256: str,
    field_patches: list[dict[str, Any]],
    require_valid: bool = True,
) -> dict[str, Any]:
    """Apply exact accepted review wording through the ordinary save transaction."""
    from .review import (
        REVIEW_PROPOSAL_APPLIED_EVENT,
        REVIEW_SCHEMA_VERSION,
        _hash_record,
        _review_root,
        _review_timestamp,
    )

    ensure_identifier(statement_id, "statement ID")
    ensure_identifier(actor, "actor ID")
    if not expected_assessment_sha256 or not isinstance(expected_assessment_sha256, str):
        raise ValueError("expected_assessment_sha256 is required")
    if not isinstance(field_patches, list) or not field_patches:
        raise ValueError("Explicit field_patches are required; acceptance is not application")

    root = _review_root(workspace, case_id)
    application_path = root / "applications" / f"{statement_id}.json"
    if application_path.exists():
        raise ValueError(f"Review proposal {statement_id} has already been applied")

    statement_path = root / "statements" / f"{statement_id}.json"
    if not statement_path.is_file():
        raise FileNotFoundError(f"Unknown review statement {statement_id}")
    statement = json.loads(statement_path.read_text(encoding="utf-8"))
    if statement.get("statement_sha256") != _hash_record(statement, "statement_sha256"):
        raise ValueError("Review statement hash is invalid")

    disposition_path = root / "dispositions" / f"{statement_id}.json"
    if not disposition_path.is_file():
        raise ValueError(f"No disposition recorded for {statement_id}; acceptance is required before apply")
    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    if disposition.get("disposition_sha256") != _hash_record(disposition, "disposition_sha256"):
        raise ValueError("Review disposition hash is invalid")
    if disposition.get("statement_sha256") != statement.get("statement_sha256"):
        raise ValueError("Disposition does not reference the current statement hash")
    disposition_value = disposition.get("disposition")
    if disposition_value == "PARTIALLY_ACCEPTED":
        raise ValueError(
            "PARTIALLY_ACCEPTED is ambiguous for one free-text proposed_change; "
            "file a successor statement containing the exact accepted wording"
        )
    if disposition_value != "ACCEPTED":
        raise ValueError(f"Disposition {disposition_value!r} cannot be applied")

    assessment_path = workspace.case_path(case_id) / "assessment.json"
    current_sha = sha256_file(assessment_path)
    if current_sha != expected_assessment_sha256:
        raise ValueError("Stale assessment: expected_assessment_sha256 does not match the current assessment")
    if statement.get("assessment_sha256") != current_sha:
        raise ValueError("Review statement is stale: assessment_sha256 no longer matches the current assessment")

    target_type = str(statement.get("target_type"))
    target_id = str(statement.get("target_id"))
    proposed_change = statement.get("proposed_change")
    if not isinstance(proposed_change, str) or not proposed_change.strip():
        raise ValueError("Accepted review statement has no exact proposed_change")
    if len(field_patches) != 1:
        raise ValueError("An accepted review statement must apply exactly one explicit field patch")
    patch = field_patches[0]
    if not isinstance(patch, dict):
        raise ValueError("field_patches[0] must be an object")
    if "target_path" not in patch or "value" not in patch:
        raise ValueError("field_patches[0] requires target_path and value")
    path = normalize_target_path(str(patch["target_path"]))
    if not path_within_review_target(path, target_type, target_id):
        raise ValueError(f"Field path outside proposal target {target_type}:{target_id}: {path}")
    if patch["value"] != proposed_change:
        raise ValueError("Review field patch value differs from the accepted proposed_change")

    statement_bytes_before = statement_path.read_bytes()
    disposition_bytes_before = disposition_path.read_bytes()
    assessment = workspace.load_case(case_id)
    before_value = get_at_path(assessment, path)
    patches_for_record = [
        {
            "target_path": path,
            "expected_value": before_value,
            "value": patch["value"],
            "before_value_sha256": sha256_bytes(canonical_json_bytes(before_value)),
            "after_value_sha256": sha256_bytes(canonical_json_bytes(patch["value"])),
        }
    ]
    authority_targets = [(target_type, target_id)]
    authority_assignments = assessment_edit_authority_assignments(workspace, case_id, actor, authority_targets)
    authority_digests = {
        str(item["assignment_id"]): str(item["assignment_sha256"]) for item in authority_assignments
    }

    patched = apply_field_patches(assessment, [{"target_path": path, "value": patch["value"]}])
    planned_bytes = json.dumps(patched, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    planned_after = sha256_bytes(planned_bytes)
    application: dict[str, Any] = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "application_id": f"RAPP-{statement_id}",
        "statement_id": statement_id,
        "statement_sha256": statement["statement_sha256"],
        "disposition": disposition_value,
        "disposition_sha256": disposition["disposition_sha256"],
        "actor": actor,
        "authority_assignments": authority_digests,
        "applied_at": _review_timestamp(),
        "field_patches": patches_for_record,
        "before_assessment_sha256": current_sha,
        "after_assessment_sha256": planned_after,
        "assessment_mutation": "ORDINARY_SAVE_CASE",
        "model_invocation": "NONE",
        "authority_profile": "LOCAL_UNAUTHENTICATED_ATTRIBUTION",
        "authority_boundary": (
            "Application attributes a local workflow assessment edit. It does not establish "
            "legal or institutional authority and does not rewrite review records in place."
        ),
    }
    application["application_sha256"] = _hash_record(application, "application_sha256")
    event_metadata = {
        "proposal_kind": "REVIEW",
        "proposal_id": statement_id,
        "proposal_sha256": statement["statement_sha256"],
        "disposition_sha256": disposition["disposition_sha256"],
        "disposition": disposition_value,
        "applied_paths": [path],
        "authority_assignments": authority_digests,
        "model_invocation": "NONE",
        "before_assessment_sha256": current_sha,
        "after_assessment_sha256": planned_after,
        "application_sha256": application["application_sha256"],
    }

    def revalidate_authority() -> None:
        current = assessment_edit_authority_assignments(workspace, case_id, actor, authority_targets)
        current_digests = {
            str(item["assignment_id"]): str(item["assignment_sha256"]) for item in current
        }
        for assignment_id, digest in authority_digests.items():
            if current_digests.get(assignment_id) != digest:
                raise ValueError("Assessment-edit authority changed before persistence")
        if get_at_path(workspace.load_case(case_id), path) != before_value:
            raise ValueError(f"Field value changed before persistence: {path}")

    save_result = workspace.save_case(
        case_id,
        patched,
        actor=actor,
        require_valid=require_valid,
        expected_sha256=expected_assessment_sha256,
        event_metadata=event_metadata,
        additional_events=[(REVIEW_PROPOSAL_APPLIED_EVENT, event_metadata)],
        exclusive_records=[(application_path, application)],
        precondition=revalidate_authority,
    )
    if save_result.get("after_sha256") != planned_after:
        raise RuntimeError("Assessment digest after ordinary save did not match the planned apply digest")
    if statement_path.read_bytes() != statement_bytes_before:
        raise RuntimeError("Review statement bytes changed during apply")
    if disposition_path.read_bytes() != disposition_bytes_before:
        raise RuntimeError("Review disposition bytes changed during apply")
    return {
        "application": application,
        "path": str(application_path),
        "save": save_result,
        "boundary": (
            "Review disposition remains separate from assessment mutation. "
            "This record links an ordinary assessment edit to a human-accepted review proposal."
        ),
    }
