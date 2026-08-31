from __future__ import annotations

import json
from typing import Any, cast
from uuid import uuid4

from ..util import canonical_json_bytes, sha256_bytes, utc_now
from .errors import DeltaCompileError, DeltaValidationError
from .schemas import (
    DECISION_TO_REGISTER,
    DELTA_BOUNDARY,
    DISPOSITION_DECISIONS,
    validate_adjudicated_delta,
    validate_adjudicated_delta_semantics,
    validate_delta_operation,
)

CHANGE_CLASS_OPERATION_DEFAULTS: dict[str, str] = {
    "REGULATORY_OR_MARKET_EVENT": "ADD_EVENT",
    "CAPITAL_AND_OWNERSHIP_EVENT": "ADD_EVENT",
    "GOVERNANCE_AND_LEADERSHIP_EVENT": "ADD_EVENT",
    "NEW_SOURCE_RECORD": "ADD_RECORD",
    "NEW_RELATIONSHIP": "ADD_RELATIONSHIP",
    "ENTITY_ALIAS": "ADD_ALIAS",
    "SOURCE_INACCESSIBILITY": "RECORD_SOURCE_INACCESSIBILITY",
    "ASSESSMENT_REOPENING": "QUEUE_ASSESSMENT_REVIEW",
    "FIELD_UPDATE": "UPDATE_FIELD_WITH_PREDECESSOR",
    "RECORD_SUPERSESSION": "SUPERSEDE_RECORD",
    "NEW_ENTITY": "ADD_ENTITY",
    "NEW_GRAPH_SOURCE": "ADD_SOURCE",
    "NEW_OBSERVATION": "ADD_OBSERVATION",
    "NEW_ASSERTION": "ADD_ASSERTION",
    "ASSERTION_SUPERSESSION": "SUPERSEDE_ASSERTION",
    "ENTITY_SUPERSESSION": "SUPERSEDE_ENTITY",
    "SOURCE_SUCCESSOR_ROUTE": "RECORD_SOURCE_SUCCESSOR_ROUTE",
    "REOPENING_DECISION": "RECORD_REOPENING_DECISION",
    "NO_CHANGE_COMPARISON": "RECORD_NO_CHANGE_COMPARISON",
}


def _adjudication_hash(adjudication: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(adjudication))


def _disposition_entry(candidate: dict[str, Any], adjudication: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate["candidate_id"],
        "adjudication_id": adjudication["adjudication_id"],
        "decided_at": adjudication["decided_at"],
        "decided_by": adjudication["decided_by"],
        "decision": adjudication["decision"],
        "change_class": adjudication.get("change_class"),
        "materiality": adjudication.get("materiality"),
        "reopening_effect": adjudication.get("reopening_effect"),
        "rationale": adjudication.get("rationale"),
        "adjudication_sha256": _adjudication_hash(adjudication),
    }


def _candidate_reference(candidate: dict[str, Any], adjudication: dict[str, Any] | None) -> dict[str, Any]:
    reference: dict[str, Any] = {
        "candidate_id": candidate["candidate_id"],
        "source_id": candidate["source_id"],
        "source_snapshot_ids": candidate.get("source_snapshot_ids", []),
        "current_snapshot_sha256": candidate["current_snapshot_sha256"],
    }
    if adjudication is not None:
        reference["adjudication_id"] = adjudication["adjudication_id"]
        reference["adjudication_sha256"] = _adjudication_hash(adjudication)
    return reference


def _normalize_operation_spec(
    spec: dict[str, Any],
    *,
    candidate: dict[str, Any],
    adjudication: dict[str, Any],
    sequence: int,
) -> dict[str, Any]:
    operation = dict(spec)
    operation.setdefault("operation_id", f"OP-{sequence:06d}")
    operation.setdefault("candidate_id", candidate["candidate_id"])
    operation.setdefault("adjudication_id", adjudication["adjudication_id"])
    return operation


def _default_operation_from_change_class(
    change_class: str,
    candidate: dict[str, Any],
    adjudication: dict[str, Any],
    sequence: int,
) -> dict[str, Any] | None:
    operation_type = CHANGE_CLASS_OPERATION_DEFAULTS.get(change_class)
    if operation_type is None:
        return None
    base: dict[str, Any] = {
        "operation_id": f"OP-{sequence:06d}",
        "operation_type": operation_type,
        "candidate_id": candidate["candidate_id"],
        "adjudication_id": adjudication["adjudication_id"],
    }
    if operation_type == "ADD_EVENT":
        base["target_section"] = "regulatory_and_market_events"
        base["record"] = {
            "event_id": f"EVT-{candidate['candidate_id'].removeprefix('CAND-')[:8]}",
            "event_date": adjudication["decided_at"][:10],
            "source_ids": [candidate["source_id"]],
            "evidence_state": "HUMAN_ADJUDICATED_CANDIDATE",
            "summary": candidate.get("summary", ""),
            "boundary": adjudication.get("boundary", DELTA_BOUNDARY),
        }
    elif operation_type == "ADD_RECORD":
        base["target_section"] = "sources"
        base["record"] = {
            "source_id": candidate["source_id"],
            "summary": candidate.get("summary", ""),
            "boundary": adjudication.get("boundary", DELTA_BOUNDARY),
        }
    elif operation_type == "RECORD_SOURCE_INACCESSIBILITY":
        base["target_section"] = "sources"
        base["source_id"] = candidate["source_id"]
        base["inaccessibility_reason"] = adjudication.get("rationale", "Source inaccessible")
        base["evidence_state"] = "SOURCE_INACCESSIBLE"
    elif operation_type == "QUEUE_ASSESSMENT_REVIEW":
        base["target_section"] = "assessment_reviews"
        base["assessment_id"] = f"ASMT-{candidate['source_id']}"
        base["reopening_effect"] = adjudication.get("reopening_effect", "REVIEW_REQUIRED")
        base["rationale"] = adjudication.get("rationale", "")
    else:
        return None
    return base


def compile_adjudicated_delta(
    refresh_package: dict[str, Any],
    predecessor: dict[str, Any],
    *,
    predecessor_release_id: str,
    operation_specs: dict[str, list[dict[str, Any]]] | None = None,
    policy_version: str = "MONITORING_POLICY_v1",
    actor: str = "local-user",
) -> dict[str, Any]:
    """Compile a non-canonical adjudicated delta from a refresh package and predecessor release."""
    metadata = refresh_package.get("metadata")
    if not isinstance(metadata, dict):
        raise DeltaCompileError("Refresh package metadata is required")
    package_version = metadata.get("version")
    if not isinstance(package_version, str) or not package_version:
        raise DeltaCompileError("Refresh package version is required")

    registry_ref = refresh_package.get("registry_reference")
    if not isinstance(registry_ref, dict):
        raise DeltaCompileError("Refresh package registry_reference is required")
    source_registry_sha256 = registry_ref.get("sha256")
    if not isinstance(source_registry_sha256, str):
        raise DeltaCompileError("Refresh package registry sha256 is required")

    predecessor_sha256 = sha256_bytes(canonical_json_bytes(predecessor))
    specs_by_candidate = operation_specs or {}

    candidates = refresh_package.get("change_candidates", [])
    adjudications = refresh_package.get("adjudications", [])
    adjudication_by_candidate = {record["candidate_id"]: record for record in adjudications if isinstance(record, dict)}

    disposition_registers: dict[str, list[dict[str, Any]]] = {
        "accepted": [],
        "rejected": [],
        "deferred": [],
        "duplicate": [],
        "needs_evidence": [],
        "unresolved": [],
    }
    candidate_references: list[dict[str, Any]] = []
    reopening_decisions: list[dict[str, Any]] = []
    operations: list[dict[str, Any]] = []
    blocked_operations: list[dict[str, Any]] = []
    operation_sequence = 1

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str):
            continue
        adjudication = adjudication_by_candidate.get(candidate_id)
        candidate_references.append(_candidate_reference(candidate, adjudication))
        if adjudication is None:
            disposition_registers["unresolved"].append(
                {
                    "candidate_id": candidate_id,
                    "status": "PENDING_HUMAN_ADJUDICATION",
                    "source_id": candidate.get("source_id", ""),
                }
            )
            continue

        decision = adjudication.get("decision")
        if decision not in DISPOSITION_DECISIONS:
            raise DeltaCompileError(f"Unsupported adjudication decision {decision!r} for {candidate_id}")
        register_key = DECISION_TO_REGISTER.get(cast(str, decision))
        if register_key is None:
            raise DeltaCompileError(f"No disposition register for decision {decision!r}")
        change_class_raw = adjudication.get("change_class", "")
        change_class = change_class_raw if isinstance(change_class_raw, str) else ""
        disposition_entry = _disposition_entry(candidate, adjudication)
        disposition_entry["change_class"] = change_class
        disposition_registers[register_key].append(disposition_entry)

        if decision != "ACCEPT":
            continue

        reopening_effect = adjudication.get("reopening_effect")
        if reopening_effect not in {"NO_EFFECT", "UNDETERMINED"}:
            reopening_decisions.append(
                {
                    "candidate_id": candidate_id,
                    "reopening_effect": reopening_effect,
                    "rationale": adjudication.get("rationale", ""),
                }
            )

        candidate_specs = specs_by_candidate.get(candidate_id, [])
        if candidate_specs:
            for spec in candidate_specs:
                operation = _normalize_operation_spec(
                    spec,
                    candidate=candidate,
                    adjudication=adjudication,
                    sequence=operation_sequence,
                )
                operations.append(operation)
                operation_sequence += 1
            continue

        default_operation = _default_operation_from_change_class(
            change_class,
            candidate,
            adjudication,
            operation_sequence,
        )
        if default_operation is None:
            blocked_operations.append(
                {
                    "candidate_id": candidate_id,
                    "code": "MISSING_OPERATION_SPEC",
                    "reason": (
                        f"Accepted candidate {candidate_id} with change_class {change_class!r} "
                        "requires explicit operation_specs"
                    ),
                }
            )
            continue
        operations.append(default_operation)
        operation_sequence += 1

    operations.sort(key=lambda item: item["operation_id"])

    delta_id = f"DELTA-{uuid4().hex}"
    delta: dict[str, Any] = {
        "metadata": {
            "title": "NeuroAI adjudicated observatory delta",
            "delta_id": delta_id,
            "version": "1.0",
            "generated_at": utc_now(),
            "generated_by": actor,
            "status": "NON_CANONICAL",
            "refresh_package_version": package_version,
            "refresh_package_sha256": sha256_bytes(canonical_json_bytes(refresh_package)),
        },
        "predecessor": {
            "release_id": predecessor_release_id,
            "sha256": predecessor_sha256,
            "source_registry_sha256": source_registry_sha256,
            "policy_version": policy_version,
        },
        "candidate_references": candidate_references,
        "operations": operations,
        "disposition_registers": disposition_registers,
        "blocked_operations": blocked_operations,
        "reopening_decisions": reopening_decisions,
        "withheld_claims": [
            "This adjudicated delta is not a canonical observatory successor release.",
            "Accepted operations do not establish substantive truth without domain review.",
            "No assessment is reopened or modified automatically.",
            "No UNESCO endorsement, regulatory decision, clinical conclusion, or conformance determination is created.",
        ],
        "boundary": DELTA_BOUNDARY,
    }

    schema_errors = validate_adjudicated_delta(delta)
    if schema_errors:
        raise DeltaValidationError(
            f"Compiled delta failed schema validation: {json.dumps(schema_errors, ensure_ascii=False)}"
        )
    semantic_errors = validate_adjudicated_delta_semantics(delta)
    if semantic_errors:
        raise DeltaValidationError(
            f"Compiled delta failed semantic validation: {json.dumps(semantic_errors, ensure_ascii=False)}"
        )
    for index, operation in enumerate(delta["operations"]):
        op_errors = validate_delta_operation(operation)
        if op_errors:
            raise DeltaValidationError(
                f"Operation {index} failed validation: {json.dumps(op_errors, ensure_ascii=False)}"
            )
    return delta
