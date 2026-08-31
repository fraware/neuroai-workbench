from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from jsonschema import Draft202012Validator

from .assessment_dependencies import (
    load_all_reference_manifests,
    match_dependency,
    validate_manifest,
)
from .monitoring import REOPENING_EFFECTS
from .observatory import KNOWN_REOPENING_DECISIONS
from .util import canonical_json_bytes, load_json, sha256_bytes, utc_now

OPERATIONS_RESOURCE_PACKAGE = "neuroai_workbench.resources.operations"
RECOMMENDATION_SCHEMA = "REOPENING_RECOMMENDATION.schema.json"
CONFIRMATION_SCHEMA = "REOPENING_HUMAN_CONFIRMATION.schema.json"

REOPENING_BOUNDARY = (
    "Reopening recommendations apply deterministic dependency rules only. Human confirmation is required before any "
    "observatory or assessment effect. No assessment record is modified automatically."
)

HUMAN_REOPENING_EFFECTS = frozenset(set(REOPENING_EFFECTS) | {"DECLINED"})

DELTA_SECTION_CHANGE_CLASS: dict[str, str] = {
    "regulatory_and_market_events": "REGULATORY_OR_MARKET_EVENT",
    "capital_and_ownership_events": "OWNERSHIP_OR_SUPPLIER_DEPENDENCY_CHANGE",
    "model_records": "MODEL_OR_SYSTEM_VERSION_CHANGE",
    "supplier_dependency_relationships": "OWNERSHIP_OR_SUPPLIER_DEPENDENCY_CHANGE",
    "governance_and_leadership_events": "GOVERNANCE_OR_LEADERSHIP_EVENT",
}

DEFAULT_POLICY_EFFECTS: dict[str, str] = {
    "REGULATORY_OR_MARKET_EVENT": "REVIEW_REQUIRED",
    "SAFETY_EVENT_OR_WITHDRAWAL": "FULL_REASSESSMENT_REQUIRED",
    "CLINICAL_TRIAL_STATUS_CHANGE": "REVIEW_REQUIRED",
    "MODEL_OR_SYSTEM_VERSION_CHANGE": "PARTIAL_REASSESSMENT_REQUIRED",
    "OWNERSHIP_OR_SUPPLIER_DEPENDENCY_CHANGE": "EVIDENCE_GAP_UPDATE",
    "GOVERNANCE_OR_LEADERSHIP_EVENT": "METADATA_UPDATE_ONLY",
}

EFFECT_TO_OBSERVATORY_DECISION: dict[str, str] = {
    "NO_EFFECT": "NO_REOPENING_TRIGGER_IDENTIFIED",
    "METADATA_UPDATE_ONLY": "METADATA_UPDATE_ONLY",
    "EVIDENCE_GAP_UPDATE": "UPDATE_REQUIRED_NO_ASSESSMENT_REOPEN",
    "REVIEW_REQUIRED": "REOPEN_REQUIRED",
    "PARTIAL_REASSESSMENT_REQUIRED": "REOPEN_REQUIRED",
    "FULL_REASSESSMENT_REQUIRED": "REOPEN_REQUIRED",
    "UNDETERMINED": "REOPEN_REQUIRED",
}


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


def _operation_id(record: dict[str, Any], section: str, index: int) -> str:
    for field in (
        "event_id",
        "dependency_id",
        "model_id",
        "governance_id",
        "decision_id",
        "source_id",
    ):
        value = record.get(field)
        if isinstance(value, str) and value:
            return value
    return f"{section}[{index}]"


def _record_tokens(record: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key, value in record.items():
        if isinstance(value, str) and value.strip():
            tokens.add(value.strip())
            tokens.add(value.strip().casefold())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    tokens.add(item.strip())
                    tokens.add(item.strip().casefold())
    return tokens


def _target_kind_for_section(section: str) -> str | None:
    mapping = {
        "regulatory_and_market_events": "REGULATORY_RECORD",
        "model_records": "MODEL",
        "supplier_dependency_relationships": "SUPPLIER",
        "governance_and_leadership_events": "ORGANIZATION",
        "capital_and_ownership_events": "ORGANIZATION",
    }
    return mapping.get(section)


def extract_delta_operations(delta: dict[str, Any]) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    if not isinstance(delta, dict):
        return operations
    for section, records in delta.items():
        if not isinstance(records, list):
            continue
        change_class = DELTA_SECTION_CHANGE_CLASS.get(section, "UNCLASSIFIED")
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            operations.append(
                {
                    "operation_id": _operation_id(record, section, index),
                    "operation_section": section,
                    "change_class": change_class,
                    "record": record,
                    "tokens": sorted(_record_tokens(record)),
                }
            )
    return operations


def _manifest_index(manifests: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for manifest in manifests.values():
        metadata = manifest.get("metadata", {})
        if isinstance(metadata, dict) and metadata.get("assessment_id"):
            indexed[str(metadata["assessment_id"])] = manifest
    return indexed


def _system_tokens(manifest: dict[str, Any]) -> set[str]:
    metadata = manifest.get("metadata", {})
    tokens: set[str] = set()
    if isinstance(metadata, dict):
        for field in ("system_id", "configuration_id", "observatory_binding"):
            value = metadata.get(field)
            if isinstance(value, str) and value.strip():
                tokens.add(value.strip())
                tokens.add(value.strip().casefold())
    return tokens


def _operation_system_tokens(record: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for field in ("system", "subject", "organization", "developer", "name"):
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            tokens.add(value.strip())
            tokens.add(value.strip().casefold())
    return tokens


def _systems_align(operation: dict[str, Any], manifest: dict[str, Any]) -> bool:
    record = operation.get("record", {})
    if not isinstance(record, dict):
        return False
    manifest_tokens = _system_tokens(manifest)
    operation_tokens = _operation_system_tokens(record)
    return bool(manifest_tokens & operation_tokens)


def _dependency_matches(operation: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    record = operation.get("record", {})
    if not isinstance(record, dict):
        return []
    section = str(operation.get("operation_section", ""))
    matches: list[str] = []
    dependencies = manifest.get("dependencies", [])
    if not isinstance(dependencies, list):
        return matches

    target_kind = _target_kind_for_section(section)
    operation_id = str(operation.get("operation_id", ""))
    if target_kind and operation_id:
        for item in match_dependency(target_kind=target_kind, target_ref=operation_id, manifest=manifest):
            dependency_id = item.get("dependency_id")
            if isinstance(dependency_id, str):
                matches.append(dependency_id)

    if section == "regulatory_and_market_events" and not matches:
        return matches

    if not _systems_align(operation, manifest):
        return matches

    tokens = set(operation.get("tokens", []))
    metadata = manifest.get("metadata", {})
    if isinstance(metadata, dict):
        for field in ("system_id", "configuration_id", "observatory_binding"):
            value = metadata.get(field)
            if isinstance(value, str) and (value in tokens or value.casefold() in tokens):
                for item in dependencies:
                    if not isinstance(item, dict):
                        continue
                    if item.get("target_ref") == value or item.get("observatory_object_ref") == value:
                        dependency_id = item.get("dependency_id")
                        if isinstance(dependency_id, str) and dependency_id not in matches:
                            matches.append(dependency_id)

    for item in dependencies:
        if not isinstance(item, dict):
            continue
        if item.get("dependency_role") not in {"REOPENING_TRIGGER", "IDENTITY_DEFINING", "FINDING_SUPPORTING"}:
            continue
        if item.get("target_kind") == "JURISDICTION" and section == "regulatory_and_market_events":
            continue
        for token_field in ("target_ref", "target_label", "observatory_object_ref"):
            token = item.get(token_field)
            if isinstance(token, str) and (token in tokens or token.casefold() in tokens):
                dependency_id = item.get("dependency_id")
                if isinstance(dependency_id, str) and dependency_id not in matches:
                    matches.append(dependency_id)
    return matches


def _has_unresolved_dependency(matches: list[str], manifest: dict[str, Any]) -> bool:
    dependencies = manifest.get("dependencies", [])
    if not isinstance(dependencies, list):
        return False
    matched = [item for item in dependencies if isinstance(item, dict) and item.get("dependency_id") in matches]
    return any(item.get("resolution_state") in {"UNKNOWN", "INACCESSIBLE"} for item in matched)


def _rule_effect(change_class: str, matches: list[str], unresolved: bool) -> str:
    if not matches:
        return "NO_EFFECT"
    if unresolved:
        return "UNDETERMINED"
    return DEFAULT_POLICY_EFFECTS.get(change_class, "REVIEW_REQUIRED")


def recommend_reopening(
    operation: dict[str, Any],
    *,
    assessment_id: str,
    manifest: dict[str, Any],
    observatory_object: str | None = None,
) -> dict[str, Any]:
    matches = _dependency_matches(operation, manifest)
    unresolved = _has_unresolved_dependency(matches, manifest)
    change_class = str(operation.get("change_class", "UNCLASSIFIED"))
    rule_effect = _rule_effect(change_class, matches, unresolved)
    if matches:
        resolution_state = "UNRESOLVED" if unresolved else "RESOLVED"
    else:
        resolution_state = "NO_MATCH"
    rationale = (
        f"Matched {len(matches)} dependency record(s) for {assessment_id} under change class {change_class}."
        if matches
        else f"No dependency match for {assessment_id}; operation remains out of scope for this assessment boundary."
    )
    if unresolved:
        rationale += " One or more matched dependencies remain UNKNOWN or INACCESSIBLE; effect is UNDETERMINED."
    basis_seed = {
        "assessment_id": assessment_id,
        "operation_id": operation.get("operation_id"),
        "operation_section": operation.get("operation_section"),
        "change_class": change_class,
        "dependency_matches": matches,
        "rule_reopening_effect": rule_effect,
    }
    recommendation_id = f"REC-{sha256_bytes(canonical_json_bytes(basis_seed))[:24].upper()}"
    recommendation = {
        "recommendation_id": recommendation_id,
        "operation_id": operation.get("operation_id"),
        "operation_section": operation.get("operation_section"),
        "assessment_id": assessment_id,
        "observatory_object": observatory_object or (manifest.get("metadata", {}) or {}).get("observatory_binding"),
        "change_class": change_class,
        "materiality": "UNDETERMINED",
        "rule_reopening_effect": rule_effect,
        "suggested_observatory_decision": EFFECT_TO_OBSERVATORY_DECISION.get(rule_effect),
        "rule_rationale": rationale,
        "dependency_matches": matches,
        "basis_ids": list(matches),
        "empty_basis": len(matches) == 0,
        "empty_basis_no_reopening_is_not_nothing_changed": True,
        "resolution_state": resolution_state,
        "assessment_mutation_performed": False,
        "boundary": REOPENING_BOUNDARY,
    }
    errors = _schema_errors(recommendation, RECOMMENDATION_SCHEMA)
    if errors:
        raise ValueError(f"Reopening recommendation failed validation: {json.dumps(errors, ensure_ascii=False)}")
    return recommendation


def analyze_observatory_delta(
    delta: dict[str, Any],
    manifests: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    manifest_map = _manifest_index(manifests or load_all_reference_manifests())
    recommendations: list[dict[str, Any]] = []
    for operation in extract_delta_operations(delta):
        for assessment_id, manifest in manifest_map.items():
            if validate_manifest(manifest)["valid"] is not True:
                continue
            recommendations.append(recommend_reopening(operation, assessment_id=assessment_id, manifest=manifest))
    return recommendations


def confirm_reopening_recommendation(
    recommendation: dict[str, Any],
    *,
    human_reopening_effect: str,
    human_rationale: str,
    confirmed_by: str,
    authority_claim: dict[str, str],
    observatory_decision: str | None = None,
) -> dict[str, Any]:
    if human_reopening_effect not in HUMAN_REOPENING_EFFECTS:
        raise ValueError(f"Unsupported human reopening effect {human_reopening_effect!r}")
    if not human_rationale.strip():
        raise ValueError("Human rationale is required")
    if not authority_claim.get("name_or_role") or not authority_claim.get("accountability_state"):
        raise ValueError("Authority claim requires name_or_role and accountability_state")
    if observatory_decision is not None and observatory_decision not in KNOWN_REOPENING_DECISIONS:
        raise ValueError(f"Unsupported observatory decision {observatory_decision!r}")

    recommendation_sha256 = sha256_bytes(canonical_json_bytes(recommendation))
    confirmation = {
        "confirmation_id": f"RCF-{uuid4().hex[:12].upper()}",
        "recommendation_id": recommendation["recommendation_id"],
        "recommendation_sha256": recommendation_sha256,
        "confirmed_at": utc_now(),
        "confirmed_by": confirmed_by,
        "authority_claim": {
            "name_or_role": authority_claim["name_or_role"],
            "organization": authority_claim.get("organization", "UNRESOLVED"),
            "accountability_state": authority_claim["accountability_state"],
        },
        "human_reopening_effect": human_reopening_effect,
        "human_rationale": human_rationale,
        "rule_reopening_effect": recommendation["rule_reopening_effect"],
        "observatory_decision": observatory_decision,
        "assessment_mutation_performed": False,
        "boundary": REOPENING_BOUNDARY,
    }
    errors = _schema_errors(confirmation, CONFIRMATION_SCHEMA)
    if errors:
        raise ValueError(f"Reopening confirmation failed validation: {json.dumps(errors, ensure_ascii=False)}")
    return confirmation


def reconcile_with_observatory_decisions(
    recommendations: list[dict[str, Any]],
    observatory_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    by_object: dict[str, dict[str, Any]] = {}
    for item in observatory_decisions:
        if isinstance(item, dict) and item.get("object"):
            by_object[str(item["object"])] = item

    rows: list[dict[str, Any]] = []
    matched_objects: set[str] = set()
    for recommendation in recommendations:
        if recommendation.get("rule_reopening_effect") == "NO_EFFECT":
            continue
        observatory_object = recommendation.get("observatory_object")
        decision_row = by_object.get(str(observatory_object), {})
        matched_objects.add(str(observatory_object))
        expected = recommendation.get("suggested_observatory_decision")
        observed = decision_row.get("decision")
        rows.append(
            {
                "assessment_id": recommendation.get("assessment_id"),
                "observatory_object": observatory_object,
                "operation_id": recommendation.get("operation_id"),
                "rule_reopening_effect": recommendation.get("rule_reopening_effect"),
                "suggested_observatory_decision": expected,
                "observed_observatory_decision": observed,
                "aligned": observed == expected if observed else None,
            }
        )

    unmatched = [
        item
        for key, item in by_object.items()
        if key not in matched_objects and item.get("decision") != "NO_REOPENING_TRIGGER_IDENTIFIED"
    ]
    return {
        "rows": rows,
        "unmatched_observatory_decisions": unmatched,
        "counts": {
            "recommendations": len(recommendations),
            "non_no_effect": sum(1 for item in recommendations if item.get("rule_reopening_effect") != "NO_EFFECT"),
            "reconciled_rows": len(rows),
            "unmatched_observatory_decisions": len(unmatched),
        },
        "boundary": REOPENING_BOUNDARY,
    }


def load_observatory_delta(path: Path) -> dict[str, Any]:
    release = load_json(path)
    if not isinstance(release, dict):
        raise ValueError("Observatory release must be a JSON object")
    delta = release.get("delta")
    if not isinstance(delta, dict):
        raise ValueError("Observatory release delta is required")
    return delta


def summarize_reopening_analysis(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    by_assessment: dict[str, list[str]] = {}
    for item in recommendations:
        assessment_id = str(item.get("assessment_id"))
        by_assessment.setdefault(assessment_id, []).append(str(item.get("rule_reopening_effect")))
    strongest: dict[str, str] = {}
    priority = [
        "FULL_REASSESSMENT_REQUIRED",
        "PARTIAL_REASSESSMENT_REQUIRED",
        "REVIEW_REQUIRED",
        "EVIDENCE_GAP_UPDATE",
        "METADATA_UPDATE_ONLY",
        "UNDETERMINED",
        "NO_EFFECT",
    ]
    for assessment_id, effects in by_assessment.items():
        for effect in priority:
            if effect in effects:
                strongest[assessment_id] = effect
                break
    return {
        "counts": {
            "recommendations": len(recommendations),
            "assessments": len(by_assessment),
        },
        "strongest_rule_effect_by_assessment": strongest,
        "boundary": REOPENING_BOUNDARY,
    }
