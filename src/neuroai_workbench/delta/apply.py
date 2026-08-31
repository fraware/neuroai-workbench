from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from ..util import atomic_write_json, canonical_json_bytes, ensure_identifier, load_json, safe_join, sha256_bytes
from .errors import DeltaApplyError, DeltaValidationError
from .schemas import validate_adjudicated_delta, validate_adjudicated_delta_semantics

APPLY_BOUNDARY = (
    "Delta application produces a candidate successor for review. It does not issue a canonical release "
    "and does not establish substantive correctness of applied changes."
)

LIST_SECTIONS = frozenset(
    {
        "sources",
        "organizations",
        "regulatory_and_market_events",
        "capital_and_ownership_events",
        "representative_model_records",
        "trial_site_relationships",
        "participant_authority_relationships",
        "supplier_dependency_relationships",
        "assessment_reviews",
        "entity_aliases",
        "entities",
        "observations",
        "assertions",
        "source_successor_routes",
        "reopening_decisions",
        "no_change_comparisons",
    }
)

GRAPH_ADD_TYPES = frozenset(
    {"ADD_RECORD", "ADD_RELATIONSHIP", "ADD_EVENT", "ADD_ENTITY", "ADD_SOURCE", "ADD_OBSERVATION", "ADD_ASSERTION"}
)
GRAPH_SUPERSEDE_TYPES = frozenset({"SUPERSEDE_RECORD", "SUPERSEDE_ASSERTION", "SUPERSEDE_ENTITY"})


def _delta_sha256(delta: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(delta))


def _find_record_index(records: list[Any], record_id_field: str, record_id: str) -> int | None:
    for index, record in enumerate(records):
        if isinstance(record, dict) and record.get(record_id_field) == record_id:
            return index
    return None


def _apply_operation(successor: dict[str, Any], operation: dict[str, Any], predecessor: dict[str, Any]) -> None:
    operation_type = operation["operation_type"]
    target_section = operation["target_section"]

    if operation_type in GRAPH_ADD_TYPES:
        record = operation.get("record")
        if not isinstance(record, dict):
            raise DeltaApplyError(f"{operation_type} requires a record object")
        section = successor.setdefault(target_section, [])
        if not isinstance(section, list):
            raise DeltaApplyError(f"Target section {target_section!r} is not a list")
        record_id_field = operation.get("record_id_field")
        record_id = operation.get("record_id")
        if record_id_field and record_id:
            existing = _find_record_index(section, record_id_field, record_id)
            if existing is not None:
                raise DeltaApplyError(f"Record {record_id!r} already exists in {target_section!r}")
        for existing_record in section:
            if isinstance(existing_record, dict) and existing_record == record:
                raise DeltaApplyError(f"Duplicate record append blocked in {target_section!r}")
        section.append(copy.deepcopy(record))
        return

    if operation_type == "UPDATE_FIELD_WITH_PREDECESSOR":
        record_id_field = operation["record_id_field"]
        record_id = operation["record_id"]
        field = operation["field"]
        before_value = operation["before_value"]
        after_value = operation["after_value"]
        pred_section = predecessor.get(target_section, [])
        succ_section = successor.setdefault(target_section, [])
        if not isinstance(pred_section, list) or not isinstance(succ_section, list):
            raise DeltaApplyError(f"Target section {target_section!r} is not a list")
        pred_index = _find_record_index(pred_section, record_id_field, record_id)
        succ_index = _find_record_index(succ_section, record_id_field, record_id)
        if pred_index is None or succ_index is None:
            raise DeltaApplyError(f"Record {record_id!r} not found in predecessor section {target_section!r}")
        pred_record = pred_section[pred_index]
        succ_record = succ_section[succ_index]
        if not isinstance(pred_record, dict) or not isinstance(succ_record, dict):
            raise DeltaApplyError(f"Record {record_id!r} is not an object")
        if pred_record.get(field) != before_value:
            raise DeltaApplyError(
                f"Before-value mismatch for {target_section}.{record_id}.{field}: "
                f"expected {before_value!r}, found {pred_record.get(field)!r}"
            )
        if succ_record.get(field) != before_value:
            raise DeltaApplyError(f"Successor state diverged before apply for {target_section}.{record_id}.{field}")
        updated = copy.deepcopy(succ_record)
        updated[field] = after_value
        succ_section[succ_index] = updated
        return

    if operation_type in GRAPH_SUPERSEDE_TYPES:
        record_id_field = operation["record_id_field"]
        record_id = operation["record_id"]
        section = successor.setdefault(target_section, [])
        if not isinstance(section, list):
            raise DeltaApplyError(f"Target section {target_section!r} is not a list")
        index = _find_record_index(section, record_id_field, record_id)
        if index is None:
            raise DeltaApplyError(f"Record {record_id!r} not found for supersession")
        updated = copy.deepcopy(section[index])
        if not isinstance(updated, dict):
            raise DeltaApplyError("Superseded record must be an object")
        updated["superseded_by"] = operation["superseded_by"]
        updated["tombstone"] = copy.deepcopy(operation["tombstone"])
        # Predecessors remain addressable; never delete the prior id.
        section[index] = updated
        return

    if operation_type == "ADD_ALIAS":
        aliases = successor.setdefault("entity_aliases", [])
        if not isinstance(aliases, list):
            raise DeltaApplyError("entity_aliases must be a list")
        entry = {"entity_id": operation["entity_id"], "alias": operation["alias"]}
        if entry in aliases:
            raise DeltaApplyError(f"Alias {operation['alias']!r} already registered")
        aliases.append(entry)
        return

    if operation_type == "RECORD_SOURCE_INACCESSIBILITY":
        source_id = operation["source_id"]
        sources = successor.get("sources", [])
        if not isinstance(sources, list):
            raise DeltaApplyError("sources must be a list")
        index = _find_record_index(sources, "source_id", source_id)
        if index is None:
            raise DeltaApplyError(f"Unknown source {source_id!r}")
        updated = copy.deepcopy(sources[index])
        if not isinstance(updated, dict):
            raise DeltaApplyError("Source record must be an object")
        updated["evidence_state"] = operation["evidence_state"]
        updated["inaccessibility_reason"] = operation["inaccessibility_reason"]
        sources[index] = updated
        return

    if operation_type == "QUEUE_ASSESSMENT_REVIEW":
        reviews = successor.setdefault("assessment_reviews", [])
        if not isinstance(reviews, list):
            raise DeltaApplyError("assessment_reviews must be a list")
        entry = {
            "assessment_id": operation["assessment_id"],
            "reopening_effect": operation["reopening_effect"],
            "rationale": operation["rationale"],
            "status": "QUEUED_FOR_HUMAN_REVIEW",
        }
        reviews.append(entry)
        return

    if operation_type == "RECORD_SOURCE_SUCCESSOR_ROUTE":
        routes = successor.setdefault("source_successor_routes", [])
        if not isinstance(routes, list):
            raise DeltaApplyError("source_successor_routes must be a list")
        entry = {
            "route_id": operation["route_id"],
            "predecessor_source_id": operation["predecessor_source_id"],
            "successor_source_id": operation["successor_source_id"],
            "rationale": operation["rationale"],
        }
        if any(isinstance(item, dict) and item.get("route_id") == entry["route_id"] for item in routes):
            raise DeltaApplyError(f"Route {entry['route_id']!r} already exists")
        routes.append(entry)
        return

    if operation_type == "RECORD_REOPENING_DECISION":
        decisions = successor.setdefault("reopening_decisions", [])
        if not isinstance(decisions, list):
            raise DeltaApplyError("reopening_decisions must be a list")
        decision = operation.get("reopening_decision")
        if not isinstance(decision, dict):
            raise DeltaApplyError("RECORD_REOPENING_DECISION requires a reopening_decision object")
        decisions.append(copy.deepcopy(decision))
        return

    if operation_type == "RECORD_NO_CHANGE_COMPARISON":
        comparisons = successor.setdefault("no_change_comparisons", [])
        if not isinstance(comparisons, list):
            raise DeltaApplyError("no_change_comparisons must be a list")
        scope = operation.get("comparison_scope")
        if not isinstance(scope, str) or not scope.strip():
            raise DeltaApplyError("RECORD_NO_CHANGE_COMPARISON requires explicit comparison_scope")
        entry = {
            "source_id": operation["source_id"],
            "comparison_scope": scope.strip(),
            "comparison_result": operation["comparison_result"],
            "rationale": operation["rationale"],
        }
        comparisons.append(entry)
        return

    raise DeltaApplyError(f"Unsupported operation type {operation_type!r}")


def apply_delta(
    predecessor: dict[str, Any],
    delta: dict[str, Any],
    output_dir: Path,
    *,
    apply_id: str,
    actor: str = "local-user",
) -> dict[str, Any]:
    """Apply a validated delta to an immutable predecessor, writing a candidate successor in output_dir."""
    ensure_identifier(apply_id, "apply ID")
    schema_errors = validate_adjudicated_delta(delta)
    if schema_errors:
        raise DeltaValidationError(f"Delta failed schema validation: {json.dumps(schema_errors, ensure_ascii=False)}")
    semantic_errors = validate_adjudicated_delta_semantics(delta)
    if semantic_errors:
        raise DeltaValidationError(
            f"Delta failed semantic validation: {json.dumps(semantic_errors, ensure_ascii=False)}"
        )

    predecessor_sha256 = sha256_bytes(canonical_json_bytes(predecessor))
    expected_sha256 = delta.get("predecessor", {}).get("sha256")
    if predecessor_sha256 != expected_sha256:
        raise DeltaApplyError(f"Predecessor sha256 mismatch: expected {expected_sha256!r}, got {predecessor_sha256!r}")

    output_root = output_dir.resolve()
    manifest_path = safe_join(output_root, "apply-manifest.json")
    if manifest_path.exists():
        existing = load_json(manifest_path)
        if isinstance(existing, dict):
            if existing.get("delta_sha256") == _delta_sha256(delta):
                raise DeltaApplyError("Refusing deterministic double-apply of the same adjudicated delta")
            raise DeltaApplyError("Refusing to overwrite an existing delta application manifest")

    immutable_predecessor = copy.deepcopy(predecessor)
    successor = copy.deepcopy(predecessor)
    for operation in delta.get("operations", []):
        if isinstance(operation, dict):
            _apply_operation(successor, operation, immutable_predecessor)

    successor["metadata"] = {
        **(successor.get("metadata", {}) if isinstance(successor.get("metadata"), dict) else {}),
        "status": "CANDIDATE_SUCCESSOR_NOT_CANONICAL",
        "derived_from_predecessor_sha256": predecessor_sha256,
        "delta_id": delta.get("metadata", {}).get("delta_id"),
        "apply_id": apply_id,
        "applied_by": actor,
        "boundary": APPLY_BOUNDARY,
    }

    successor_path = safe_join(output_root, "candidate-successor.json")
    if successor_path.exists():
        raise DeltaApplyError("Refusing to overwrite an existing candidate successor")
    atomic_write_json(successor_path, successor)

    manifest = {
        "apply_id": apply_id,
        "applied_by": actor,
        "delta_id": delta.get("metadata", {}).get("delta_id"),
        "delta_sha256": _delta_sha256(delta),
        "predecessor_sha256": predecessor_sha256,
        "successor_sha256": sha256_bytes(canonical_json_bytes(successor)),
        "operation_count": len(delta.get("operations", [])),
        "status": "CANDIDATE_SUCCESSOR_NOT_CANONICAL",
        "boundary": APPLY_BOUNDARY,
    }
    atomic_write_json(manifest_path, manifest)

    if sha256_bytes(canonical_json_bytes(predecessor)) != predecessor_sha256:
        raise DeltaApplyError("Predecessor was mutated during application")

    return {
        "apply_id": apply_id,
        "manifest": manifest,
        "successor_path": str(successor_path.relative_to(output_root)),
        "predecessor_sha256": predecessor_sha256,
        "predecessor_unchanged": sha256_bytes(canonical_json_bytes(predecessor)) == predecessor_sha256,
        "boundary": APPLY_BOUNDARY,
    }


def apply_delta_from_paths(
    predecessor_path: Path,
    delta_path: Path,
    output_dir: Path,
    *,
    apply_id: str,
    actor: str = "local-user",
) -> dict[str, Any]:
    predecessor = load_json(predecessor_path)
    delta = load_json(delta_path)
    if not isinstance(predecessor, dict) or not isinstance(delta, dict):
        raise ValueError("Predecessor and delta must be JSON objects")
    return apply_delta(predecessor, delta, output_dir, apply_id=apply_id, actor=actor)
