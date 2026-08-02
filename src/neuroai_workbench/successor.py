from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from jsonschema import Draft202012Validator

from .observatory import validate_release
from .reopening import analyze_observatory_delta, extract_delta_operations
from .util import canonical_json_bytes, ensure_identifier, load_json, sha256_bytes, utc_now

OPERATIONS_RESOURCE_PACKAGE = "neuroai_workbench.resources.operations"
CANDIDATE_SCHEMA = "SUCCESSOR_CANDIDATE.schema.json"
GATE_SCHEMA = "SUCCESSOR_RELEASE_GATE.schema.json"

RELEASE_GATES = ("CANDIDATE", "REVIEWED", "AUTHORIZED", "PUBLISHED")
GATE_ORDER = {gate: index for index, gate in enumerate(RELEASE_GATES)}

SUCCESSOR_BOUNDARY = (
    "Successor packages are release-control artifacts. Gate advancement records local authority claims only. "
    "Publication never occurs automatically and does not establish substantive truth, authorization, or conformance."
)

DEFAULT_WITHHELD_CLAIMS = [
    "Candidate successor status does not confer canonical observatory authority.",
    "Gate advancement records named local authority claims only; they are not authenticated institutional delegation.",
    "No UNESCO endorsement, regulatory authorization, clinical recommendation, or conformance determination is created.",
    "Historical predecessor releases remain immutable.",
    "Missing or inaccessible evidence is not converted into demonstrated failure.",
]


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


def _delta_counts(delta: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for section, records in delta.items():
        if isinstance(records, list):
            counts[section] = len(records)
    return counts


def _inventory_from_delta(delta: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    changed: list[dict[str, str]] = []
    for section, records in delta.items():
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            record_id = next(
                (
                    str(record[key])
                    for key in ("event_id", "dependency_id", "model_id", "governance_id", "decision_id")
                    if isinstance(record.get(key), str) and record.get(key)
                ),
                "",
            )
            if record_id:
                changed.append({"section": section, "record_id": record_id})
    return {
        "changed": changed,
        "unchanged": [],
        "superseded": [],
        "unresolved": [],
    }


def generate_successor_candidate(
    predecessor: dict[str, Any],
    *,
    delta: dict[str, Any],
    version: str,
    evidence_cutoff: str,
    effective_as_of: str,
    predecessor_sha256: str,
    reopening_confirmations: list[dict[str, Any]] | None = None,
    observatory_decisions: list[dict[str, Any]] | None = None,
    actor: str = "local-user",
    withheld_claims: list[str] | None = None,
) -> dict[str, Any]:
    ensure_identifier(version, "successor version")
    predecessor_metadata = predecessor.get("metadata", {})
    if not isinstance(predecessor_metadata, dict):
        raise ValueError("Predecessor metadata is required")
    predecessor_version = str(predecessor_metadata.get("version", ""))
    if not predecessor_version:
        raise ValueError("Predecessor version is required")

    recommendations = analyze_observatory_delta(delta)
    operations = extract_delta_operations(delta)
    candidate_id = f"SC-{uuid4().hex[:12].upper()}"
    baseline = predecessor.get("baseline_reference", {})
    baseline_sha256 = baseline.get("canonical_sha256") if isinstance(baseline, dict) else None

    candidate_body: dict[str, Any] = {
        "metadata": {
            "title": f"NeuroAI observatory successor candidate {version}",
            "candidate_id": candidate_id,
            "version": version,
            "predecessor_version": predecessor_version,
            "effective_as_of": effective_as_of,
            "evidence_cutoff": evidence_cutoff,
            "generated_at": utc_now(),
            "generated_by": actor,
            "status": "CANDIDATE",
        },
        "predecessor_reference": {
            "release_version": predecessor_version,
            "sha256": predecessor_sha256,
            "immutable": True,
            **({"baseline_sha256": baseline_sha256} if isinstance(baseline_sha256, str) else {}),
        },
        "delta_reference": {
            "delta_counts": _delta_counts(delta),
            "operation_count": len(operations),
            "adjudicated_delta_sha256": sha256_bytes(canonical_json_bytes(delta)),
        },
        "reopening_register": {
            "recommendations": recommendations,
            "confirmations": reopening_confirmations or [],
            "observatory_decisions": observatory_decisions or [],
        },
        "inventories": _inventory_from_delta(delta),
        "data_quality_report": {
            "predecessor_validation_required": True,
            "referential_closure_required": True,
            "duplicate_detection_required": True,
            "reopening_reconciliation_required": True,
            "human_readable_comparison_required": True,
        },
        "release_gate": {"current_gate": "CANDIDATE", "history": []},
        "withheld_claims": withheld_claims or list(DEFAULT_WITHHELD_CLAIMS),
        "boundary": SUCCESSOR_BOUNDARY,
    }
    candidate_body["metadata"]["canonical_sha256"] = sha256_bytes(canonical_json_bytes(candidate_body))
    errors = _schema_errors(candidate_body, CANDIDATE_SCHEMA)
    if errors:
        raise ValueError(f"Successor candidate failed validation: {json.dumps(errors, ensure_ascii=False)}")
    return candidate_body


def validate_successor_candidate(value: dict[str, Any]) -> dict[str, Any]:
    errors = list(_schema_errors(value, CANDIDATE_SCHEMA))
    metadata = value.get("metadata", {})
    recorded_sha = metadata.get("canonical_sha256") if isinstance(metadata, dict) else None
    payload = dict(value)
    if isinstance(payload.get("metadata"), dict):
        payload["metadata"] = dict(payload["metadata"])
        payload["metadata"].pop("canonical_sha256", None)
    computed_sha = sha256_bytes(canonical_json_bytes(payload))
    if isinstance(recorded_sha, str) and recorded_sha != computed_sha:
        errors.append(
            {
                "code": "CANDIDATE_SHA256_MISMATCH",
                "path": "metadata.canonical_sha256",
                "expected": computed_sha,
                "observed": recorded_sha,
            }
        )
    return {
        "valid": not errors,
        "errors": errors,
        "current_gate": value.get("release_gate", {}).get("current_gate"),
        "boundary": SUCCESSOR_BOUNDARY,
    }


def _next_gate(current: str) -> str | None:
    order = GATE_ORDER[current]
    if order + 1 >= len(RELEASE_GATES):
        return None
    return RELEASE_GATES[order + 1]


def advance_release_gate(
    candidate: dict[str, Any],
    *,
    target_gate: str,
    authority_claim: dict[str, str],
    rationale: str,
    actor: str = "local-user",
    verification_checks: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Advance a successor candidate one sequential release gate.

    AUTHORIZED and PUBLISHED require named local authority claims and sequential
    progression only. They do not require issue #10 independent-review disposition
    completeness. Independent review remains optional follow-up documentation.
    """
    if target_gate not in RELEASE_GATES or target_gate == "CANDIDATE":
        raise ValueError(f"Unsupported target gate {target_gate!r}")
    if not rationale.strip():
        raise ValueError("Gate advancement rationale is required")
    for field in ("name_or_role", "authority_basis", "accountability_state"):
        if not authority_claim.get(field):
            raise ValueError(f"Authority claim requires {field}")

    report = validate_successor_candidate(candidate)
    if not report["valid"]:
        raise ValueError("Successor candidate failed validation")

    release_gate = candidate.get("release_gate", {})
    current_gate = release_gate.get("current_gate", "CANDIDATE")
    if current_gate not in GATE_ORDER:
        raise ValueError(f"Unsupported current gate {current_gate!r}")
    expected_next = _next_gate(current_gate)
    if target_gate != expected_next:
        raise ValueError(f"Gate advancement must proceed sequentially; expected {expected_next!r}, got {target_gate!r}")

    metadata = dict(candidate.get("metadata", {}))
    candidate_id = str(metadata.get("candidate_id"))
    candidate_sha256 = str(metadata.get("canonical_sha256"))

    gate_record = {
        "gate_record_id": f"GATE-{uuid4().hex[:12].upper()}",
        "candidate_id": candidate_id,
        "candidate_sha256": candidate_sha256,
        "prior_gate": current_gate,
        "target_gate": target_gate,
        "advanced_at": utc_now(),
        "advanced_by": actor,
        "authority_claim": {
            "name_or_role": authority_claim["name_or_role"],
            "authority_basis": authority_claim["authority_basis"],
            "organization": authority_claim.get("organization", "UNRESOLVED"),
            "accountability_state": authority_claim["accountability_state"],
        },
        "rationale": rationale,
        "verification_checks": verification_checks
        or [
            "schema_validation",
            "predecessor_hash_reconciliation",
            "reopening_reconciliation",
        ],
        "automatic_publication_performed": False,
        "boundary": SUCCESSOR_BOUNDARY,
    }
    gate_errors = _schema_errors(gate_record, GATE_SCHEMA)
    if gate_errors:
        raise ValueError(f"Release gate record failed validation: {json.dumps(gate_errors, ensure_ascii=False)}")

    updated = json.loads(json.dumps(candidate))
    updated["metadata"]["status"] = target_gate
    updated["release_gate"]["current_gate"] = target_gate
    updated["release_gate"]["history"].append(gate_record)
    updated["metadata"].pop("canonical_sha256", None)
    updated["metadata"]["canonical_sha256"] = sha256_bytes(canonical_json_bytes(updated))

    if target_gate == "PUBLISHED" and current_gate != "AUTHORIZED":
        raise ValueError("Publication requires prior AUTHORIZED gate; automatic publication is prohibited")

    return updated, gate_record


def verify_predecessor_reference(candidate: dict[str, Any], predecessor_bytes: bytes) -> list[dict[str, Any]]:
    predecessor_reference = candidate.get("predecessor_reference", {})
    if not isinstance(predecessor_reference, dict):
        return [{"code": "PREDECESSOR_REFERENCE_REQUIRED", "path": "predecessor_reference"}]
    expected = predecessor_reference.get("sha256")
    observed = sha256_bytes(predecessor_bytes)
    if not isinstance(expected, str):
        return [{"code": "PREDECESSOR_SHA256_REQUIRED", "path": "predecessor_reference.sha256"}]
    if expected != observed:
        return [
            {
                "code": "PREDECESSOR_SHA256_MISMATCH",
                "path": "predecessor_reference.sha256",
                "expected": expected,
                "observed": observed,
            }
        ]
    return []


def reconcile_reopening_register(candidate: dict[str, Any]) -> dict[str, Any]:
    register = candidate.get("reopening_register", {})
    recommendations = register.get("recommendations", []) if isinstance(register, dict) else []
    confirmations = register.get("confirmations", []) if isinstance(register, dict) else []
    decisions = register.get("observatory_decisions", []) if isinstance(register, dict) else []
    confirmed_ids = {item.get("recommendation_id") for item in confirmations if isinstance(item, dict)}
    unresolved = [
        item.get("recommendation_id")
        for item in recommendations
        if isinstance(item, dict)
        and item.get("rule_reopening_effect") not in {"NO_EFFECT", "UNDETERMINED"}
        and item.get("recommendation_id") not in confirmed_ids
    ]
    return {
        "counts": {
            "recommendations": len(recommendations) if isinstance(recommendations, list) else 0,
            "confirmations": len(confirmations) if isinstance(confirmations, list) else 0,
            "observatory_decisions": len(decisions) if isinstance(decisions, list) else 0,
            "unresolved_material_recommendations": len(unresolved),
        },
        "unresolved_recommendation_ids": [item for item in unresolved if item],
        "boundary": SUCCESSOR_BOUNDARY,
    }


def generate_from_observatory_release(
    release_path: Path,
    *,
    version: str,
    actor: str = "local-user",
) -> dict[str, Any]:
    predecessor = load_json(release_path)
    if not isinstance(predecessor, dict):
        raise ValueError("Observatory release must be a JSON object")
    predecessor_report = validate_release(predecessor)
    if not predecessor_report["valid"]:
        raise ValueError("Predecessor observatory release failed validation")
    metadata = predecessor.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("Predecessor metadata is required")
    delta = predecessor.get("delta")
    if not isinstance(delta, dict):
        raise ValueError("Predecessor delta is required for candidate generation")
    return generate_successor_candidate(
        predecessor,
        delta=delta,
        version=version,
        evidence_cutoff=str(metadata.get("effective_as_of") or metadata.get("evidence_cutoff")),
        effective_as_of=str(metadata.get("effective_as_of")),
        predecessor_sha256=str(predecessor_report["canonical_sha256"]),
        observatory_decisions=predecessor.get("reopening_decisions", [])
        if isinstance(predecessor.get("reopening_decisions"), list)
        else [],
        actor=actor,
    )


def summarize_successor_candidate(value: dict[str, Any]) -> dict[str, Any]:
    report = validate_successor_candidate(value)
    metadata = value.get("metadata", {}) if isinstance(value.get("metadata"), dict) else {}
    return {
        "valid": report["valid"],
        "candidate_id": metadata.get("candidate_id"),
        "version": metadata.get("version"),
        "predecessor_version": metadata.get("predecessor_version"),
        "current_gate": value.get("release_gate", {}).get("current_gate"),
        "operation_count": value.get("delta_reference", {}).get("operation_count"),
        "withheld_claims": value.get("withheld_claims", []),
        "boundary": SUCCESSOR_BOUNDARY,
    }
