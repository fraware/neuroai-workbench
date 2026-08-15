from __future__ import annotations

import json
from collections import Counter
from importlib.resources import files
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from jsonschema import Draft202012Validator

from .events import load_events, verify_chain
from .governance_opinions import REVIEW_TRACKS
from .governance_transactions import append_governance_record_locked, governance_serialized
from .successor import validate_successor_candidate
from .util import canonical_json_bytes, load_json, sha256_bytes, utc_now
from .workspace import Workspace

RESOURCE_PACKAGE = "neuroai_workbench.resources.operations"
POLICY_RESOURCE = "RELEASE_ATTESTATION_POLICY.v1.json"
ATTESTATION_SCHEMA = "RELEASE_ATTESTATION.schema.json"
PUBLICATION_SCHEMA = "ATTESTED_PUBLICATION.schema.json"
PROFILE = "DEFAULT_RELEASE_ATTESTATION"
ATTESTATION_EVENT = "RELEASE_ATTESTATION_RECORDED"
PUBLICATION_EVENT = "ATTESTED_RELEASE_PUBLICATION_RECORDED"
PRIVATE_KEYS = frozenset({"_path"})

ATTESTATION_BOUNDARY = (
    "Default release attestation records one designated maintainer's six-domain repository release judgment over "
    "exact candidate and product digests. It does not establish scientific, clinical, regulatory, legal, "
    "conformance, institutional, or external authority."
)
PUBLICATION_BOUNDARY = (
    "Publication records bind one active authorized default release attestation to explicit publication evidence. "
    "Recording publication does not publish content automatically or establish scientific, clinical, regulatory, "
    "legal, conformance, institutional, or external authority."
)


def _resource(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(files(RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")))


def load_release_attestation_policy() -> dict[str, Any]:
    policy = _resource(POLICY_RESOURCE)
    expected = {
        "schema_version": "1",
        "policy_id": "RELATTEST-1.0.0",
        "policy_version": "1.0.0",
        "profile": PROFILE,
        "designated_authority_key": "fraware",
        "track_states": ["PASS", "BLOCK"],
        "decision_states": ["AUTHORIZE", "WITHHOLD"],
        "boundary": ATTESTATION_BOUNDARY,
    }
    if any(policy.get(key) != value for key, value in expected.items()):
        raise ValueError("Release attestation policy is invalid")
    tracks = policy.get("required_tracks")
    if not isinstance(tracks, list) or len(tracks) != len(REVIEW_TRACKS) or set(tracks) != set(REVIEW_TRACKS):
        raise ValueError("Release attestation policy must require exactly the six review domains")
    return policy


def release_attestation_policy_sha256() -> str:
    return sha256_bytes(canonical_json_bytes(load_release_attestation_policy()))


def _schema_errors(value: dict[str, Any], schema_name: str) -> list[str]:
    validator = Draft202012Validator(_resource(schema_name))
    return [
        f"{'.'.join(str(part) for part in error.absolute_path)}: {error.message}"
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _hash(record: dict[str, Any], field: str) -> str:
    controlled = {key: value for key, value in record.items() if key not in PRIVATE_KEYS and key != field}
    return sha256_bytes(canonical_json_bytes(controlled))


def _candidate_artifact_sha256(candidate: dict[str, Any]) -> str:
    payload = json.dumps(candidate, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    return sha256_bytes(payload)


def _root(workspace: Workspace, name: str) -> Path:
    root = workspace.root / "governance" / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def _load(workspace: Workspace, name: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(_root(workspace, name).glob("*.json")):
        value = load_json(path)
        if not isinstance(value, dict):
            raise ValueError(f"{name} record {path.name} must be an object")
        record = cast(dict[str, Any], value)
        record["_path"] = str(path)
        records.append(record)
    return records


def load_release_attestations(workspace: Workspace) -> list[dict[str, Any]]:
    return _load(workspace, "release-attestations")


def load_attested_publications(workspace: Workspace) -> list[dict[str, Any]]:
    return _load(workspace, "release-publications")


def _products(items: list[dict[str, str]]) -> list[dict[str, str]]:
    if not items:
        raise ValueError("At least one product digest is required")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        product_id = str(item.get("product_id", "")).strip()
        if not product_id or product_id in seen:
            raise ValueError("Product identifiers must be non-empty and unique")
        seen.add(product_id)
        result.append({"product_id": product_id, "sha256": _digest(item.get("sha256"), f"product {product_id}")})
    return sorted(result, key=lambda item: item["product_id"])


def _assessments(items: list[dict[str, str]]) -> list[dict[str, str]]:
    required = set(REVIEW_TRACKS)
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        track = str(item.get("track", "")).strip()
        state = str(item.get("state", "")).strip()
        rationale = str(item.get("rationale", "")).strip()
        if track not in required or track in seen:
            raise ValueError("Release attestation must contain each review domain exactly once")
        if state not in {"PASS", "BLOCK"} or not rationale:
            raise ValueError(f"Track {track} requires PASS/BLOCK and a rationale")
        seen.add(track)
        result.append({"track": track, "state": state, "rationale": rationale})
    if seen != required:
        raise ValueError("Release attestation must contain each review domain exactly once")
    return sorted(result, key=lambda item: item["track"])


def _conditions(items: list[dict[str, str]] | None) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items or []:
        condition_id = str(item.get("condition_id", "")).strip()
        status = str(item.get("status", "")).strip()
        effect = str(item.get("release_effect", "")).strip()
        summary = str(item.get("summary", "")).strip()
        if not condition_id or condition_id in seen:
            raise ValueError("Condition identifiers must be non-empty and unique")
        if status not in {"OPEN", "RESOLVED"} or effect not in {"BLOCKS_RELEASE", "NON_BLOCKING"} or not summary:
            raise ValueError(f"Condition {condition_id} is invalid")
        seen.add(condition_id)
        result.append({"condition_id": condition_id, "status": status, "release_effect": effect, "summary": summary})
    return sorted(result, key=lambda item: item["condition_id"])


def _designated(actor: str) -> None:
    designated = str(load_release_attestation_policy()["designated_authority_key"])
    if actor != designated:
        raise ValueError(f"Release decision actor must match designated authority {designated}")


def _active(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    superseded = {str(item["supersedes_attestation_id"]) for item in records if item.get("supersedes_attestation_id")}
    return [item for item in records if str(item.get("attestation_id", "")) not in superseded]


def _events(workspace: Workspace, action: str) -> Counter[tuple[str, str]]:
    path = workspace.root / "events.jsonl"
    if not path.exists():
        return Counter()
    report = verify_chain(path)
    if report.get("valid") is not True or report.get("trailer_valid") is not True:
        raise ValueError("Event chain is invalid")
    result: Counter[tuple[str, str]] = Counter()
    for event in load_events(path):
        payload = event.get("payload")
        if event.get("action") != action or not isinstance(payload, dict):
            continue
        prefix = "attestation" if action == ATTESTATION_EVENT else "publication"
        result[(str(payload.get(f"{prefix}_id", "")), str(payload.get(f"{prefix}_sha256", "")))] += 1
    return result


def verify_release_attestations(workspace: Workspace) -> dict[str, Any]:
    records = load_release_attestations(workspace)
    errors: list[str] = []
    try:
        events = _events(workspace, ATTESTATION_EVENT)
    except ValueError as exc:
        events = Counter()
        errors.append(str(exc))
    index = {str(item.get("attestation_id", "")): item for item in records}
    if len(index) != len(records):
        errors.append("Duplicate attestation_id")
    superseded = Counter(str(item["supersedes_attestation_id"]) for item in records if item.get("supersedes_attestation_id"))
    policy_ref = {
        "policy_id": "RELATTEST-1.0.0",
        "policy_version": "1.0.0",
        "policy_sha256": release_attestation_policy_sha256(),
    }
    for record in records:
        target = {key: value for key, value in record.items() if key not in PRIVATE_KEYS}
        attestation_id = str(target.get("attestation_id", ""))
        if target.get("attestation_sha256") != _hash(record, "attestation_sha256"):
            errors.append(f"{attestation_id}: hash mismatch")
        if _schema_errors(target, ATTESTATION_SCHEMA):
            errors.append(f"{attestation_id}: schema invalid")
        if target.get("policy_reference") != policy_ref or target.get("recorded_by") != "fraware":
            errors.append(f"{attestation_id}: authority/policy binding mismatch")
        if events[(attestation_id, str(target.get("attestation_sha256", "")))] != 1:
            errors.append(f"{attestation_id}: matching append-only event missing or duplicated")
        prior_id = target.get("supersedes_attestation_id")
        if prior_id:
            prior = index.get(str(prior_id))
            if prior is None:
                errors.append(f"{attestation_id}: supersession target missing")
            elif prior.get("candidate_reference", {}).get("candidate_artifact_sha256") != target.get("candidate_reference", {}).get("candidate_artifact_sha256"):
                errors.append(f"{attestation_id}: supersession changes the exact candidate object")
    if any(count != 1 for count in superseded.values()):
        errors.append("An attestation is superseded more than once")
    active = _active(records)
    counts = Counter(str(item.get("candidate_reference", {}).get("candidate_artifact_sha256", "")) for item in active)
    if any(digest and count > 1 for digest, count in counts.items()):
        errors.append("One exact candidate object has multiple active attestations")
    return {"valid": not errors, "errors": errors, "record_count": len(records), "active_count": len(active)}


@governance_serialized
def record_release_attestation(
    workspace: Workspace,
    *,
    candidate: dict[str, Any],
    products: list[dict[str, str]],
    track_assessments: list[dict[str, str]],
    decision: str,
    decision_rationale: str,
    conditions: list[dict[str, str]] | None = None,
    supersedes_attestation_id: str | None = None,
    actor: str = "local-user",
) -> dict[str, Any]:
    _designated(actor)
    if validate_successor_candidate(candidate).get("valid") is not True:
        raise ValueError("Successor candidate failed validation")
    if verify_release_attestations(workspace)["valid"] is not True:
        raise ValueError("Release-attestation store is invalid")
    assessments = _assessments(track_assessments)
    normalized_conditions = _conditions(conditions)
    rationale = decision_rationale.strip()
    if decision not in {"AUTHORIZE", "WITHHOLD"} or not rationale:
        raise ValueError("Decision must be AUTHORIZE/WITHHOLD with a rationale")
    if decision == "AUTHORIZE":
        if any(item["state"] == "BLOCK" for item in assessments):
            raise ValueError("AUTHORIZE is forbidden when a review domain is BLOCK")
        if any(item["status"] == "OPEN" and item["release_effect"] == "BLOCKS_RELEASE" for item in normalized_conditions):
            raise ValueError("AUTHORIZE is forbidden with an unresolved release blocker")
    metadata = candidate.get("metadata")
    predecessor = candidate.get("predecessor_reference")
    withheld_claims = candidate.get("withheld_claims")
    if not isinstance(metadata, dict) or not isinstance(predecessor, dict):
        raise ValueError("Candidate metadata and predecessor reference are required")
    if not isinstance(withheld_claims, list) or not withheld_claims:
        raise ValueError("Candidate withheld claims must be non-empty")
    candidate_ref = {
        "candidate_id": str(metadata.get("candidate_id", "")).strip(),
        "candidate_sha256": _digest(metadata.get("canonical_sha256"), "candidate canonical digest"),
        "candidate_artifact_sha256": _candidate_artifact_sha256(candidate),
    }
    predecessor_ref = {
        "release_version": str(predecessor.get("release_version", "")).strip(),
        "sha256": _digest(predecessor.get("sha256"), "predecessor digest"),
    }
    if not candidate_ref["candidate_id"] or not predecessor_ref["release_version"]:
        raise ValueError("Candidate and predecessor identifiers are required")
    active = _active(load_release_attestations(workspace))
    same_object = [
        item
        for item in active
        if item.get("candidate_reference", {}).get("candidate_artifact_sha256") == candidate_ref["candidate_artifact_sha256"]
    ]
    if supersedes_attestation_id is None and same_object:
        raise ValueError("Exact candidate object already has an active attestation")
    if supersedes_attestation_id is not None and not any(item.get("attestation_id") == supersedes_attestation_id for item in same_object):
        raise ValueError("Supersession must reference the active attestation for the same exact object")
    policy = load_release_attestation_policy()
    attestation_id = f"RELATT-{uuid4().hex[:20].upper()}"
    record: dict[str, Any] = {
        "schema_version": "1",
        "attestation_id": attestation_id,
        "recorded_at": utc_now(),
        "recorded_by": actor,
        "profile": PROFILE,
        "policy_reference": {
            "policy_id": str(policy["policy_id"]),
            "policy_version": str(policy["policy_version"]),
            "policy_sha256": release_attestation_policy_sha256(),
        },
        "candidate_reference": candidate_ref,
        "predecessor_reference": predecessor_ref,
        "products": _products(products),
        "withheld_claims_sha256": sha256_bytes(canonical_json_bytes(withheld_claims)),
        "track_assessments": assessments,
        "conditions": normalized_conditions,
        "decision": decision,
        "decision_rationale": rationale,
        "boundary": ATTESTATION_BOUNDARY,
    }
    if supersedes_attestation_id is not None:
        record["supersedes_attestation_id"] = supersedes_attestation_id
    record["attestation_sha256"] = _hash(record, "attestation_sha256")
    errors = _schema_errors(record, ATTESTATION_SCHEMA)
    if errors:
        raise ValueError("Release attestation failed schema validation: " + "; ".join(errors))
    output = _root(workspace, "release-attestations") / f"{attestation_id}.json"
    append_governance_record_locked(
        workspace,
        record_path=output,
        record=record,
        record_id=attestation_id,
        record_sha256=str(record["attestation_sha256"]),
        event_action=ATTESTATION_EVENT,
        actor=actor,
        event_payload={
            "attestation_id": attestation_id,
            "attestation_sha256": record["attestation_sha256"],
            "candidate_artifact_sha256": candidate_ref["candidate_artifact_sha256"],
            "decision": decision,
        },
        secondary_digests={
            "candidate_sha256": str(candidate_ref["candidate_sha256"]),
            "candidate_artifact_sha256": str(candidate_ref["candidate_artifact_sha256"]),
            "policy_sha256": str(record["policy_reference"]["policy_sha256"]),
            "withheld_claims_sha256": str(record["withheld_claims_sha256"]),
        },
    )
    return {"attestation": record, "path": str(output)}


def verify_attested_publications(workspace: Workspace) -> dict[str, Any]:
    records = load_attested_publications(workspace)
    errors: list[str] = []
    if verify_release_attestations(workspace)["valid"] is not True:
        errors.append("Release-attestation store is invalid")
    try:
        events = _events(workspace, PUBLICATION_EVENT)
    except ValueError as exc:
        events = Counter()
        errors.append(str(exc))
    active = {str(item["attestation_id"]): item for item in _active(load_release_attestations(workspace))}
    refs: Counter[str] = Counter()
    ids: Counter[str] = Counter()
    for record in records:
        target = {key: value for key, value in record.items() if key not in PRIVATE_KEYS}
        publication_id = str(target.get("publication_id", ""))
        ids[publication_id] += 1
        if target.get("publication_sha256") != _hash(record, "publication_sha256"):
            errors.append(f"{publication_id}: hash mismatch")
        if _schema_errors(target, PUBLICATION_SCHEMA):
            errors.append(f"{publication_id}: schema invalid")
        if target.get("recorded_by") != "fraware":
            errors.append(f"{publication_id}: wrong designated authority")
        reference = target.get("attestation_reference", {})
        attestation_id = str(reference.get("attestation_id", "")) if isinstance(reference, dict) else ""
        refs[attestation_id] += 1
        attestation = active.get(attestation_id)
        if (
            attestation is None
            or attestation.get("decision") != "AUTHORIZE"
            or not isinstance(reference, dict)
            or reference.get("attestation_sha256") != attestation.get("attestation_sha256")
            or target.get("candidate_reference") != attestation.get("candidate_reference")
        ):
            errors.append(f"{publication_id}: active authorization binding mismatch")
        if events[(publication_id, str(target.get("publication_sha256", "")))] != 1:
            errors.append(f"{publication_id}: matching append-only event missing or duplicated")
    if any(publication_id and count > 1 for publication_id, count in ids.items()):
        errors.append("Duplicate publication_id")
    if any(attestation_id and count > 1 for attestation_id, count in refs.items()):
        errors.append("An attestation has multiple publication records")
    return {"valid": not errors, "errors": errors, "record_count": len(records)}


@governance_serialized
def record_attested_publication(
    workspace: Workspace,
    *,
    attestation_id: str,
    publication_evidence: dict[str, str],
    actor: str = "local-user",
) -> dict[str, Any]:
    _designated(actor)
    if verify_release_attestations(workspace)["valid"] is not True:
        raise ValueError("Release-attestation store is invalid")
    if verify_attested_publications(workspace)["valid"] is not True:
        raise ValueError("Attested-publication store is invalid")
    active = {str(item["attestation_id"]): item for item in _active(load_release_attestations(workspace))}
    attestation = active.get(attestation_id)
    if attestation is None or attestation.get("decision") != "AUTHORIZE":
        raise ValueError("Publication requires one active AUTHORIZE attestation")
    if any(item.get("attestation_reference", {}).get("attestation_id") == attestation_id for item in load_attested_publications(workspace)):
        raise ValueError("Release attestation already has a publication record")
    reference = str(publication_evidence.get("reference", "")).strip()
    if not reference.startswith(("public-ref:", "protected-ref:")) or reference in {"public-ref:", "protected-ref:"}:
        raise ValueError("Publication evidence requires a non-empty public-ref: or protected-ref:")
    evidence = {"reference": reference, "sha256": _digest(publication_evidence.get("sha256"), "publication evidence")}
    publication_id = f"RELPUB-{uuid4().hex[:20].upper()}"
    record: dict[str, Any] = {
        "schema_version": "1",
        "publication_id": publication_id,
        "recorded_at": utc_now(),
        "recorded_by": actor,
        "attestation_reference": {
            "attestation_id": attestation_id,
            "attestation_sha256": str(attestation["attestation_sha256"]),
        },
        "candidate_reference": attestation["candidate_reference"],
        "publication_evidence": evidence,
        "automatic_publication_performed": False,
        "boundary": PUBLICATION_BOUNDARY,
    }
    record["publication_sha256"] = _hash(record, "publication_sha256")
    errors = _schema_errors(record, PUBLICATION_SCHEMA)
    if errors:
        raise ValueError("Attested publication failed schema validation: " + "; ".join(errors))
    output = _root(workspace, "release-publications") / f"{publication_id}.json"
    append_governance_record_locked(
        workspace,
        record_path=output,
        record=record,
        record_id=publication_id,
        record_sha256=str(record["publication_sha256"]),
        event_action=PUBLICATION_EVENT,
        actor=actor,
        event_payload={
            "publication_id": publication_id,
            "publication_sha256": record["publication_sha256"],
            "attestation_id": attestation_id,
            "candidate_artifact_sha256": attestation["candidate_reference"]["candidate_artifact_sha256"],
        },
        secondary_digests={
            "attestation_sha256": str(attestation["attestation_sha256"]),
            "candidate_artifact_sha256": str(attestation["candidate_reference"]["candidate_artifact_sha256"]),
            "publication_evidence_sha256": str(evidence["sha256"]),
        },
    )
    return {"publication": record, "path": str(output)}
