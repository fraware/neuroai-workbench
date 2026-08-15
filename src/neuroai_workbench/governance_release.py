from __future__ import annotations

import json
from collections import Counter
from importlib.resources import files
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from jsonschema import Draft202012Validator

from .events import load_events, verify_chain
from .governance_policy import (
    SINGLE_AUTHORITY_MODEL,
    evaluate_governance_completion,
    governance_policy_sha256,
    load_governance_completion_policy,
)
from .governance_scope import load_governance_scope_manifests
from .governance_transactions import append_governance_record_locked, governance_serialized
from .successor import validate_successor_candidate
from .util import canonical_json_bytes, load_json, sha256_bytes, utc_now
from .workspace import Workspace

OPERATIONS_RESOURCE_PACKAGE = "neuroai_workbench.resources.operations"
RELEASE_DECISION_SCHEMA = "GOVERNANCE_RELEASE_DECISION.schema.json"
SCHEMA_VERSION = "1"
RUNTIME_PRIVATE_KEYS = frozenset({"_path"})
REAL_AUTHORITY_ACCOUNTABILITY_STATE = "CLAIMED_EXTERNAL_RELEASE_AUTHORITY"
REAL_GOVERNANCE_EXECUTION_MODE = "PROTECTED_REAL_GOVERNANCE"

RELEASE_READINESS_BOUNDARY = (
    "Release readiness packages are deterministic non-authorizing workflow evaluations over exact release and "
    "governance inputs. They do not authenticate reviewers or release authorities, establish institutional or legal "
    "delegation, authorize a canonical successor, confer UNESCO endorsement, or authorize publication."
)
RELEASE_DECISION_BOUNDARY = (
    "Release-decision records bind claimed external authority workflow evidence to exact governance and release "
    "inputs. The software does not authenticate the claimant, establish institutional or legal delegation, establish "
    "scientific or regulatory truth, confer UNESCO endorsement, or perform publication automatically."
)


def _schema() -> dict[str, Any]:
    resource = files(OPERATIONS_RESOURCE_PACKAGE).joinpath(RELEASE_DECISION_SCHEMA)
    return cast(dict[str, Any], json.loads(resource.read_text(encoding="utf-8")))


def _schema_errors(value: Any) -> list[str]:
    validator = Draft202012Validator(_schema())
    return [
        f"{'.'.join(str(part) for part in error.absolute_path)}: {error.message}"
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def _assert_digest(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a 64-character lowercase hexadecimal SHA-256 digest")
    return value


def _decisions_root(workspace: Workspace) -> Path:
    root = workspace.root / "governance" / "release-decisions"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _decision_hash(record: dict[str, Any]) -> str:
    controlled = {
        key: value for key, value in record.items() if key not in RUNTIME_PRIVATE_KEYS and key != "decision_sha256"
    }
    return sha256_bytes(canonical_json_bytes(controlled))


def load_governance_release_decisions(workspace: Workspace) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    root = _decisions_root(workspace)
    for path in sorted(root.glob("*.json")):
        value = load_json(path)
        if not isinstance(value, dict):
            raise ValueError(f"Governance release decision {path.name} must be an object")
        record = cast(dict[str, Any], value)
        record["_path"] = str(path)
        records.append(record)
    return records


def _normalize_products(products: list[dict[str, str]]) -> list[dict[str, str]]:
    if not products:
        raise ValueError("At least one release product digest is required")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, product in enumerate(products):
        if not isinstance(product, dict):
            raise ValueError(f"products[{index}] must be an object")
        product_id = str(product.get("product_id", "")).strip()
        if not product_id:
            raise ValueError(f"products[{index}].product_id is required")
        if product_id in seen:
            raise ValueError(f"Duplicate product_id {product_id}")
        seen.add(product_id)
        normalized.append(
            {
                "product_id": product_id,
                "sha256": _assert_digest(product.get("sha256"), f"products[{index}].sha256"),
            }
        )
    return sorted(normalized, key=lambda item: item["product_id"])


def _legacy_gate_classification(candidate: dict[str, Any]) -> str:
    gate = candidate.get("release_gate")
    if not isinstance(gate, dict):
        return "INVALID_GATE_STATE"
    current = str(gate.get("current_gate", ""))
    history = gate.get("history", [])
    if not isinstance(history, list):
        history = []
    authorizing_history = any(
        isinstance(item, dict) and item.get("target_gate") in {"AUTHORIZED", "PUBLISHED"} for item in history
    )
    if current in {"AUTHORIZED", "PUBLISHED"} or authorizing_history:
        return "LEGACY_LOCAL_AUTHORITY_CLAIM_NOT_GOVERNANCE_COMPLETE"
    return "NON_AUTHORIZING_CORE_GATE"


def _candidate_artifact_sha256(candidate: dict[str, Any]) -> str:
    """Hash the exact UTF-8 JSON serialization used by atomic_write_json."""
    payload = json.dumps(candidate, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    return sha256_bytes(payload)


def _scope_candidate_artifact_sha256(
    workspace: Workspace,
    *,
    scope_id: str,
    scope_sha256: str,
) -> str | None:
    manifests = [
        manifest
        for manifest in load_governance_scope_manifests(workspace)
        if manifest.get("scope_id") == scope_id and manifest.get("manifest_sha256") == scope_sha256
    ]
    if len(manifests) != 1:
        return None
    objects = manifests[0].get("objects")
    if not isinstance(objects, list):
        return None
    candidates = [item for item in objects if isinstance(item, dict) and item.get("role") == "SUCCESSOR_CANDIDATE"]
    if len(candidates) != 1:
        return None
    digest = candidates[0].get("sha256")
    try:
        return _assert_digest(digest, "governance_scope.SUCCESSOR_CANDIDATE.sha256")
    except ValueError:
        return None


def _evaluation_refs(evaluation: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    binding = evaluation.get("input_binding")
    if not isinstance(binding, dict):
        return [], []
    opinions_raw = binding.get("opinion_records", [])
    dispositions_raw = binding.get("owner_disposition_records", [])
    opinions = [
        {
            "opinion_id": str(item.get("opinion_id", "")),
            "opinion_sha256": str(item.get("opinion_sha256", "")),
        }
        for item in opinions_raw
        if isinstance(item, dict)
    ]
    dispositions = [
        {
            "disposition_id": str(item.get("disposition_id", "")),
            "disposition_sha256": str(item.get("disposition_sha256", "")),
            "condition_register_sha256": str(item.get("condition_register_sha256", "")),
        }
        for item in dispositions_raw
        if isinstance(item, dict)
    ]
    return opinions, dispositions


def build_release_readiness_package(
    workspace: Workspace,
    *,
    candidate: dict[str, Any],
    scope_id: str,
    scope_sha256: str,
    products: list[dict[str, str]],
) -> dict[str, Any]:
    """Build deterministic readiness evidence without performing release authorization."""
    candidate_report = validate_successor_candidate(candidate)
    if candidate_report.get("valid") is not True:
        raise ValueError("Successor candidate failed validation")
    normalized_products = _normalize_products(products)
    metadata = candidate.get("metadata")
    predecessor = candidate.get("predecessor_reference")
    if not isinstance(metadata, dict) or not isinstance(predecessor, dict):
        raise ValueError("Candidate metadata and predecessor reference are required")
    candidate_id = str(metadata.get("candidate_id", ""))
    candidate_sha256 = _assert_digest(metadata.get("canonical_sha256"), "candidate.metadata.canonical_sha256")
    candidate_artifact_sha256 = _candidate_artifact_sha256(candidate)
    predecessor_sha256 = _assert_digest(predecessor.get("sha256"), "candidate.predecessor_reference.sha256")
    scope_sha256 = _assert_digest(scope_sha256, "scope_sha256")
    scope_artifact_sha256 = _scope_candidate_artifact_sha256(
        workspace,
        scope_id=scope_id,
        scope_sha256=scope_sha256,
    )

    evaluation = evaluate_governance_completion(
        workspace,
        scope_id=scope_id,
        scope_sha256=scope_sha256,
    )
    opinions, dispositions = _evaluation_refs(evaluation)
    blockers: list[str] = []
    legacy_classification = _legacy_gate_classification(candidate)
    if legacy_classification != "NON_AUTHORIZING_CORE_GATE":
        blockers.append("LEGACY_LOCAL_AUTHORITY_GATE_PRESENT")
    if scope_artifact_sha256 is None:
        blockers.append("SCOPE_CANDIDATE_ARTIFACT_MISSING")
    elif scope_artifact_sha256 != candidate_artifact_sha256:
        blockers.append("SCOPE_CANDIDATE_ARTIFACT_MISMATCH")
    if evaluation.get("integrity_valid") is not True:
        blockers.append("GOVERNANCE_INPUT_INTEGRITY_INVALID")
    if evaluation.get("release_readiness") != "SATISFIED":
        blockers.append("GOVERNANCE_POLICY_UNSATISFIED")
    release_blockers = sorted(
        {
            str(condition_id)
            for track in evaluation.get("track_results", {}).values()
            if isinstance(track, dict)
            for condition_id in track.get("release_blocking_condition_ids", [])
        }
    )
    if release_blockers:
        blockers.append("UNRESOLVED_RELEASE_BLOCKING_CONDITIONS")

    withheld_claims = candidate.get("withheld_claims")
    if not isinstance(withheld_claims, list) or not withheld_claims:
        raise ValueError("Candidate withheld claims must be a non-empty list")
    withheld_claims_sha256 = sha256_bytes(canonical_json_bytes(withheld_claims))
    policy_ref = {
        "evaluation_id": str(evaluation.get("evaluation_id", "")),
        "evaluation_sha256": _assert_digest(evaluation.get("evaluation_sha256"), "evaluation.evaluation_sha256"),
        "input_binding_sha256": _assert_digest(
            evaluation.get("input_binding_sha256"),
            "evaluation.input_binding_sha256",
        ),
        "policy_id": str(evaluation.get("policy_id", "")),
        "policy_version": str(evaluation.get("policy_version", "")),
        "policy_sha256": _assert_digest(evaluation.get("policy_sha256"), "evaluation.policy_sha256"),
    }
    package: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "readiness_state": "READY_FOR_REAL_AUTHORITY_REVIEW" if not blockers else "NOT_READY",
        "candidate_reference": {
            "candidate_id": candidate_id,
            "candidate_sha256": candidate_sha256,
            "candidate_artifact_sha256": candidate_artifact_sha256,
            "scope_artifact_sha256": scope_artifact_sha256,
        },
        "predecessor_reference": {
            "release_version": str(predecessor.get("release_version", "")),
            "sha256": predecessor_sha256,
        },
        "governance_scope_reference": {
            "scope_id": scope_id,
            "scope_sha256": scope_sha256,
        },
        "reviewer_opinions": opinions,
        "owner_dispositions": dispositions,
        "policy_evaluation_reference": policy_ref,
        "products": normalized_products,
        "withheld_claims_sha256": withheld_claims_sha256,
        "legacy_gate_classification": legacy_classification,
        "release_blocking_condition_ids": release_blockers,
        "blocker_codes": blockers,
        "release_authorization_performed": False,
        "canonical_successor_authorized": False,
        "publication_authorized": False,
        "authority_profile": "READINESS_EVIDENCE_ONLY",
        "boundary": RELEASE_READINESS_BOUNDARY,
    }
    package_sha256 = sha256_bytes(canonical_json_bytes(package))
    package["package_sha256"] = package_sha256
    package["package_id"] = f"GOVREADY-{package_sha256[:24]}"
    return package


def _normalize_authority_claim(claim: dict[str, str]) -> dict[str, str]:
    required = ("name_or_role", "organization", "authority_basis")
    normalized = {key: str(claim.get(key, "")).strip() for key in required}
    for key in required:
        if not normalized[key]:
            raise ValueError(f"release authority claim requires {key}")
    accountability = str(claim.get("accountability_state", ""))
    execution_mode = str(claim.get("execution_mode", ""))
    if accountability != REAL_AUTHORITY_ACCOUNTABILITY_STATE:
        raise ValueError(
            "AUTHORIZED/PUBLISHED requires the reserved CLAIMED_EXTERNAL_RELEASE_AUTHORITY accountability state"
        )
    if execution_mode != REAL_GOVERNANCE_EXECUTION_MODE:
        raise ValueError("Synthetic or local execution cannot create AUTHORIZED/PUBLISHED decisions")
    evidence_reference = str(claim.get("authority_evidence_reference", "")).strip()
    if not evidence_reference.startswith("protected-ref:") or len(evidence_reference) <= len("protected-ref:"):
        raise ValueError("Release authority evidence must use a non-empty protected-ref: reference")
    return {
        **normalized,
        "accountability_state": accountability,
        "execution_mode": execution_mode,
        "authority_evidence_reference": evidence_reference,
        "authority_evidence_sha256": _assert_digest(
            claim.get("authority_evidence_sha256"),
            "authority_evidence_sha256",
        ),
    }


def _normalize_publication_evidence(evidence: dict[str, str]) -> dict[str, str]:
    reference = str(evidence.get("reference", "")).strip()
    if not reference.startswith(("public-ref:", "protected-ref:")):
        raise ValueError("Publication evidence reference must use public-ref: or protected-ref:")
    if reference in {"public-ref:", "protected-ref:"}:
        raise ValueError("Publication evidence reference cannot be empty")
    return {
        "reference": reference,
        "sha256": _assert_digest(evidence.get("sha256"), "publication_evidence.sha256"),
    }


def _package_reference(package: dict[str, Any]) -> dict[str, str]:
    return {
        "package_id": str(package.get("package_id", "")),
        "package_sha256": _assert_digest(package.get("package_sha256"), "readiness_package.package_sha256"),
    }


def _decision_core(
    *,
    decision_id: str,
    decision_type: str,
    package: dict[str, Any],
    authority_claim: dict[str, str],
    actor: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "decision_id": decision_id,
        "decision_type": decision_type,
        "decision_state": "AUTHORIZED" if decision_type == "AUTHORIZATION" else "PUBLISHED",
        "recorded_at": utc_now(),
        "recorded_by": actor,
        "candidate_reference": package["candidate_reference"],
        "predecessor_reference": package["predecessor_reference"],
        "governance_scope_reference": package["governance_scope_reference"],
        "reviewer_opinions": package["reviewer_opinions"],
        "owner_dispositions": package["owner_dispositions"],
        "policy_evaluation_reference": package["policy_evaluation_reference"],
        "products": package["products"],
        "withheld_claims_sha256": package["withheld_claims_sha256"],
        "readiness_package_reference": _package_reference(package),
        "release_authority_claim": authority_claim,
        "automatic_publication_performed": False,
        "external_authority_authenticated": False,
        "authority_profile": "CLAIMED_EXTERNAL_RELEASE_AUTHORITY_WORKFLOW_RECORD",
        "boundary": RELEASE_DECISION_BOUNDARY,
    }


def _ensure_ready(package: dict[str, Any]) -> None:
    if package.get("readiness_state") != "READY_FOR_REAL_AUTHORITY_REVIEW":
        raise ValueError("Governance release package is not ready for real authority review")
    if package.get("blocker_codes"):
        raise ValueError("Governance release package contains blockers")
    if package.get("release_blocking_condition_ids"):
        raise ValueError("Governance release package contains unresolved release-blocking conditions")


def _require_designated_authority_actor(package: dict[str, Any], actor: str) -> str:
    policy = load_governance_completion_policy(version="current")
    if policy.get("authority_model") != SINGLE_AUTHORITY_MODEL:
        raise ValueError("Current governance policy does not define a single designated authority")
    designated = str(policy.get("designated_authority_key", "")).strip()
    if not designated:
        raise ValueError("Current governance policy has no designated authority")
    policy_reference = package.get("policy_evaluation_reference")
    if not isinstance(policy_reference, dict):
        raise ValueError("Readiness package is missing its policy evaluation reference")
    expected_policy_sha256 = governance_policy_sha256(policy)
    if (
        policy_reference.get("policy_id") != policy.get("policy_id")
        or policy_reference.get("policy_version") != policy.get("policy_version")
        or policy_reference.get("policy_sha256") != expected_policy_sha256
    ):
        raise ValueError("Readiness package is not bound to the current designated-authority policy")
    if actor != designated:
        raise ValueError(f"Final decision actor must match designated governance authority {designated}")
    return designated


def _event_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_id": record["decision_id"],
        "decision_sha256": record["decision_sha256"],
        "decision_type": record["decision_type"],
        "decision_state": record["decision_state"],
        "candidate_id": record["candidate_reference"]["candidate_id"],
        "candidate_sha256": record["candidate_reference"]["candidate_sha256"],
        "candidate_artifact_sha256": record["candidate_reference"]["candidate_artifact_sha256"],
        "scope_candidate_artifact_sha256": record["candidate_reference"]["scope_artifact_sha256"],
        "scope_id": record["governance_scope_reference"]["scope_id"],
        "scope_sha256": record["governance_scope_reference"]["scope_sha256"],
        "readiness_package_sha256": record["readiness_package_reference"]["package_sha256"],
        "policy_evaluation_sha256": record["policy_evaluation_reference"]["evaluation_sha256"],
        "automatic_publication_performed": False,
        "external_authority_authenticated": False,
    }


@governance_serialized
def record_release_authorization(
    workspace: Workspace,
    *,
    candidate: dict[str, Any],
    scope_id: str,
    scope_sha256: str,
    products: list[dict[str, str]],
    authority_claim: dict[str, str],
    actor: str = "local-user",
) -> dict[str, Any]:
    package = build_release_readiness_package(
        workspace,
        candidate=candidate,
        scope_id=scope_id,
        scope_sha256=scope_sha256,
        products=products,
    )
    _ensure_ready(package)
    claim = _normalize_authority_claim(authority_claim)
    existing_report = verify_governance_release_decisions(workspace)
    if existing_report["valid"] is not True:
        raise ValueError("Governance release-decision store is invalid")
    candidate_id = str(package["candidate_reference"]["candidate_id"])
    for existing in load_governance_release_decisions(workspace):
        if (
            existing.get("decision_type") == "AUTHORIZATION"
            and existing.get("candidate_reference", {}).get("candidate_id") == candidate_id
        ):
            raise ValueError(f"Candidate {candidate_id} already has an authorization decision")

    decision_id = f"GOVREL-AUTH-{uuid4().hex[:16].upper()}"
    record = _decision_core(
        decision_id=decision_id,
        decision_type="AUTHORIZATION",
        package=package,
        authority_claim=claim,
        actor=actor,
    )
    record["decision_sha256"] = _decision_hash(record)
    errors = _schema_errors(record)
    if errors:
        raise ValueError("Governance release authorization failed schema validation: " + "; ".join(errors))
    _require_designated_authority_actor(package, actor)
    output = _decisions_root(workspace) / f"{decision_id}.json"
    append_governance_record_locked(
        workspace,
        record_path=output,
        record=record,
        record_id=decision_id,
        record_sha256=str(record["decision_sha256"]),
        event_action="GOVERNANCE_RELEASE_AUTHORIZATION_RECORDED",
        actor=actor,
        event_payload=_event_payload(record),
        secondary_digests={
            "candidate_sha256": str(record["candidate_reference"]["candidate_sha256"]),
            "candidate_artifact_sha256": str(record["candidate_reference"]["candidate_artifact_sha256"]),
            "scope_candidate_artifact_sha256": str(record["candidate_reference"]["scope_artifact_sha256"]),
            "readiness_package_sha256": str(record["readiness_package_reference"]["package_sha256"]),
            "policy_evaluation_sha256": str(record["policy_evaluation_reference"]["evaluation_sha256"]),
            "authority_evidence_sha256": str(claim["authority_evidence_sha256"]),
        },
    )
    return {"decision": record, "readiness_package": package, "path": str(output)}


@governance_serialized
def record_release_publication(
    workspace: Workspace,
    *,
    candidate: dict[str, Any],
    scope_id: str,
    scope_sha256: str,
    products: list[dict[str, str]],
    authorization_decision_id: str,
    authority_claim: dict[str, str],
    publication_evidence: dict[str, str],
    actor: str = "local-user",
) -> dict[str, Any]:
    package = build_release_readiness_package(
        workspace,
        candidate=candidate,
        scope_id=scope_id,
        scope_sha256=scope_sha256,
        products=products,
    )
    _ensure_ready(package)
    claim = _normalize_authority_claim(authority_claim)
    evidence = _normalize_publication_evidence(publication_evidence)
    verification = verify_governance_release_decisions(workspace)
    if verification["valid"] is not True:
        raise ValueError("Governance release-decision store is invalid")
    records = load_governance_release_decisions(workspace)
    matches = [record for record in records if record.get("decision_id") == authorization_decision_id]
    if len(matches) != 1:
        raise ValueError("Publication requires one exact prior authorization decision")
    authorization = matches[0]
    if authorization.get("decision_type") != "AUTHORIZATION" or authorization.get("decision_state") != "AUTHORIZED":
        raise ValueError("Publication predecessor is not an AUTHORIZED decision")
    if authorization.get("readiness_package_reference") != _package_reference(package):
        raise ValueError("Publication readiness package differs from the prior authorization")
    if authorization.get("candidate_reference") != package["candidate_reference"]:
        raise ValueError("Publication candidate differs from the prior authorization")
    if any(
        record.get("decision_type") == "PUBLICATION"
        and record.get("prior_authorization_reference", {}).get("decision_id") == authorization_decision_id
        for record in records
    ):
        raise ValueError("Authorization decision already has a publication decision")

    decision_id = f"GOVREL-PUB-{uuid4().hex[:16].upper()}"
    record = _decision_core(
        decision_id=decision_id,
        decision_type="PUBLICATION",
        package=package,
        authority_claim=claim,
        actor=actor,
    )
    record["prior_authorization_reference"] = {
        "decision_id": str(authorization["decision_id"]),
        "decision_sha256": str(authorization["decision_sha256"]),
    }
    record["publication_evidence"] = evidence
    record["decision_sha256"] = _decision_hash(record)
    errors = _schema_errors(record)
    if errors:
        raise ValueError("Governance publication decision failed schema validation: " + "; ".join(errors))
    _require_designated_authority_actor(package, actor)
    output = _decisions_root(workspace) / f"{decision_id}.json"
    append_governance_record_locked(
        workspace,
        record_path=output,
        record=record,
        record_id=decision_id,
        record_sha256=str(record["decision_sha256"]),
        event_action="GOVERNANCE_RELEASE_PUBLICATION_RECORDED",
        actor=actor,
        event_payload=_event_payload(record),
        secondary_digests={
            "candidate_sha256": str(record["candidate_reference"]["candidate_sha256"]),
            "candidate_artifact_sha256": str(record["candidate_reference"]["candidate_artifact_sha256"]),
            "scope_candidate_artifact_sha256": str(record["candidate_reference"]["scope_artifact_sha256"]),
            "readiness_package_sha256": str(record["readiness_package_reference"]["package_sha256"]),
            "prior_authorization_sha256": str(authorization["decision_sha256"]),
            "publication_evidence_sha256": str(evidence["sha256"]),
        },
    )
    return {"decision": record, "readiness_package": package, "path": str(output)}


def verify_governance_release_decisions(workspace: Workspace) -> dict[str, Any]:
    errors: list[str] = []
    records = load_governance_release_decisions(workspace)
    seen: set[str] = set()
    try:
        events = load_events(workspace.root / "events.jsonl")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        events = []
        errors.append(f"event log load failed: {exc}")
    event_counts: Counter[tuple[str, str, str]] = Counter(
        (
            str(event.get("payload", {}).get("decision_id", "")),
            str(event.get("payload", {}).get("decision_sha256", "")),
            str(event.get("action", "")),
        )
        for event in events
        if event.get("action")
        in {"GOVERNANCE_RELEASE_AUTHORIZATION_RECORDED", "GOVERNANCE_RELEASE_PUBLICATION_RECORDED"}
        and isinstance(event.get("payload"), dict)
    )
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        decision_id = str(record.get("decision_id", ""))
        if decision_id in seen:
            errors.append(f"decision {decision_id}: duplicate decision_id")
        seen.add(decision_id)
        index[decision_id] = record
        unsupported = sorted(key for key in record if key.startswith("_") and key not in RUNTIME_PRIVATE_KEYS)
        if unsupported:
            errors.append(f"decision {decision_id}: unsupported private fields {unsupported}")
        target = {key: value for key, value in record.items() if key not in RUNTIME_PRIVATE_KEYS}
        if target.get("decision_sha256") != _decision_hash(record):
            errors.append(f"decision {decision_id}: hash mismatch")
        if _schema_errors(target):
            errors.append(f"decision {decision_id}: schema invalid")
        if record.get("boundary") != RELEASE_DECISION_BOUNDARY:
            errors.append(f"decision {decision_id}: authority boundary mismatch")
        if record.get("external_authority_authenticated") is not False:
            errors.append(f"decision {decision_id}: external authority authentication must remain false")
        if record.get("automatic_publication_performed") is not False:
            errors.append(f"decision {decision_id}: automatic publication must remain false")
        candidate_reference = record.get("candidate_reference")
        if isinstance(candidate_reference, dict) and (
            candidate_reference.get("candidate_artifact_sha256") != candidate_reference.get("scope_artifact_sha256")
        ):
            errors.append(f"decision {decision_id}: candidate artifact differs from governance-scope artifact")
        action = (
            "GOVERNANCE_RELEASE_AUTHORIZATION_RECORDED"
            if record.get("decision_type") == "AUTHORIZATION"
            else "GOVERNANCE_RELEASE_PUBLICATION_RECORDED"
        )
        count = event_counts[(decision_id, str(record.get("decision_sha256", "")), action)]
        if count == 0:
            errors.append(f"decision {decision_id}: matching append-only event is missing")
        elif count > 1:
            errors.append(f"decision {decision_id}: multiple matching append-only events")

    authorizations_by_candidate: Counter[str] = Counter()
    publications_by_authorization: Counter[str] = Counter()
    for record in records:
        decision_id = str(record.get("decision_id", ""))
        candidate_ref = record.get("candidate_reference")
        candidate_id = str(candidate_ref.get("candidate_id", "")) if isinstance(candidate_ref, dict) else ""
        if record.get("decision_type") == "AUTHORIZATION":
            authorizations_by_candidate[candidate_id] += 1
            continue
        prior = record.get("prior_authorization_reference")
        if not isinstance(prior, dict):
            errors.append(f"decision {decision_id}: publication lacks prior authorization reference")
            continue
        prior_id = str(prior.get("decision_id", ""))
        authorization = index.get(prior_id)
        if authorization is None:
            errors.append(f"decision {decision_id}: prior authorization {prior_id} is missing")
            continue
        if authorization.get("decision_type") != "AUTHORIZATION":
            errors.append(f"decision {decision_id}: prior decision {prior_id} is not an authorization")
        if authorization.get("decision_sha256") != prior.get("decision_sha256"):
            errors.append(f"decision {decision_id}: prior authorization hash mismatch")
        if authorization.get("candidate_reference") != record.get("candidate_reference"):
            errors.append(f"decision {decision_id}: candidate differs from prior authorization")
        if authorization.get("readiness_package_reference") != record.get("readiness_package_reference"):
            errors.append(f"decision {decision_id}: readiness package differs from prior authorization")
        publications_by_authorization[prior_id] += 1

    for candidate_id, count in sorted(authorizations_by_candidate.items()):
        if count > 1:
            errors.append(f"candidate {candidate_id}: {count} authorization decisions recorded")
    for authorization_id, count in sorted(publications_by_authorization.items()):
        if count > 1:
            errors.append(f"authorization {authorization_id}: {count} publication decisions recorded")

    chain = verify_chain(workspace.root / "events.jsonl")
    if not chain.get("valid") or chain.get("trailer_valid") is not True:
        errors.extend(f"event chain: {error}" for error in chain.get("errors", []))
        errors.extend(f"event chain trailer: {error}" for error in chain.get("trailer_errors", []))
    return {
        "valid": not errors,
        "errors": errors,
        "counts": {
            "decisions": len(records),
            "authorizations": sum(1 for item in records if item.get("decision_type") == "AUTHORIZATION"),
            "publications": sum(1 for item in records if item.get("decision_type") == "PUBLICATION"),
        },
        "external_authority_authenticated": False,
        "automatic_publication_performed": False,
        "boundary": RELEASE_DECISION_BOUNDARY,
    }


def verify_release_decision_binding(
    workspace: Workspace,
    *,
    decision_id: str,
    candidate: dict[str, Any],
    scope_id: str,
    scope_sha256: str,
    products: list[dict[str, str]],
) -> dict[str, Any]:
    store = verify_governance_release_decisions(workspace)
    errors = list(store["errors"])
    matches = [
        record for record in load_governance_release_decisions(workspace) if record.get("decision_id") == decision_id
    ]
    if len(matches) != 1:
        errors.append(f"decision {decision_id}: expected exactly one stored decision")
        return {"valid": False, "errors": errors, "boundary": RELEASE_DECISION_BOUNDARY}
    decision = matches[0]
    package = build_release_readiness_package(
        workspace,
        candidate=candidate,
        scope_id=scope_id,
        scope_sha256=scope_sha256,
        products=products,
    )
    expected_package = _package_reference(package)
    if decision.get("readiness_package_reference") != expected_package:
        errors.append(f"decision {decision_id}: readiness package drift")
    for field in (
        "candidate_reference",
        "predecessor_reference",
        "governance_scope_reference",
        "reviewer_opinions",
        "owner_dispositions",
        "policy_evaluation_reference",
        "products",
        "withheld_claims_sha256",
    ):
        if decision.get(field) != package.get(field):
            errors.append(f"decision {decision_id}: {field} binding drift")
    return {
        "valid": not errors,
        "errors": errors,
        "decision_id": decision_id,
        "readiness_state": package["readiness_state"],
        "external_authority_authenticated": False,
        "automatic_publication_performed": False,
        "boundary": RELEASE_DECISION_BOUNDARY,
    }
