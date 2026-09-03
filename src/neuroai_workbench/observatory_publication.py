"""Lightweight explicit authorization/publication records for S2 Observatory releases.

The Observatory launch path does not require the Workbench's six-domain institutional
release-attestation profile. It still preserves the core authority invariant: candidate,
authorization, and publication are separate immutable states. Public /v1 may serve only
a candidate with one active AUTHORIZE record and one matching publication record.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .observatory_s2_release import verify_observatory_v2_s2_candidate
from .util import atomic_write_json, canonical_json_bytes, sha256_bytes, utc_now

DESIGNATED_OPERATOR = "fraware"
AUTHORIZATION_BOUNDARY = (
    "Explicit Observatory S2 operator authorization over one exact candidate manifest. Authorization is a release "
    "decision only; it does not establish scientific, clinical, regulatory, legal, conformance, or institutional truth."
)
PUBLICATION_BOUNDARY = (
    "Observatory S2 publication record binding one active AUTHORIZE record to one exact candidate representation "
    "and public publication evidence. Publication does not alter underlying substantive claims."
)


class ObservatoryPublicationError(ValueError):
    """Raised when authorization/publication state is missing, ambiguous, or incorrectly bound."""


def _digest_record(record: dict[str, Any], digest_field: str) -> str:
    controlled = {key: value for key, value in record.items() if key != digest_field and key != "_path"}
    return sha256_bytes(canonical_json_bytes(controlled))


def _require_hex(value: Any, *, length: int, field: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(char not in "0123456789abcdef" for char in value):
        raise ObservatoryPublicationError(f"{field} must be lowercase {length}-character hexadecimal")
    return value


def _load_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ObservatoryPublicationError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ObservatoryPublicationError(f"{label} must be an object")
    return value


def _candidate_reference(release_dir: Path) -> dict[str, Any]:
    candidate_errors = verify_observatory_v2_s2_candidate(release_dir)
    if candidate_errors:
        raise ObservatoryPublicationError(f"S2 candidate is invalid: {candidate_errors}")
    descriptor = _load_object(release_dir / "descriptor.json", label="S2 descriptor")
    manifest = _load_object(release_dir / "manifest.json", label="S2 manifest")
    predecessor = descriptor.get("s2_predecessor")
    if not isinstance(predecessor, dict):
        raise ObservatoryPublicationError("S2 candidate predecessor reference is missing")
    return {
        "candidate_id": str(descriptor.get("candidate_id") or ""),
        "release_tag": str(descriptor.get("release_tag") or ""),
        "manifest_sha256": _require_hex(manifest.get("manifest_sha256"), length=64, field="manifest_sha256"),
        "descriptor_sha256": _require_hex(manifest.get("descriptor_sha256"), length=64, field="descriptor_sha256"),
        "candidate_content_sha256": _require_hex(
            descriptor.get("candidate_content_sha256"), length=64, field="candidate_content_sha256"
        ),
        "workbench_compatibility_version": str(descriptor.get("workbench_compatibility_version") or ""),
        "producer_workbench_commit": _require_hex(
            descriptor.get("producer_workbench_commit"), length=40, field="producer_workbench_commit"
        ),
        "runtime_execution_pin": _require_hex(
            descriptor.get("runtime_execution_pin"), length=40, field="runtime_execution_pin"
        ),
        "observatory_graph_schema_version": str(descriptor.get("observatory_graph_schema_version") or ""),
        "s2_predecessor_release_tag": str(predecessor.get("release_tag") or ""),
        "s2_predecessor_commit": _require_hex(predecessor.get("commit"), length=40, field="s2_predecessor_commit"),
    }


def _governance_root(release_dir: Path) -> Path:
    root = release_dir / "governance"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _authorization_root(release_dir: Path) -> Path:
    root = _governance_root(release_dir) / "authorizations"
    root.mkdir(parents=True, exist_ok=True)
    return root


def load_s2_authorizations(release_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    root = release_dir / "governance" / "authorizations"
    if not root.is_dir():
        return records
    for path in sorted(root.glob("*.json")):
        record = _load_object(path, label=f"authorization {path.name}")
        record["_path"] = str(path)
        records.append(record)
    return records


def load_s2_publication(release_dir: Path) -> dict[str, Any] | None:
    path = release_dir / "governance" / "publication.json"
    if not path.is_file():
        return None
    record = _load_object(path, label="publication")
    record["_path"] = str(path)
    return record


def _active_authorizations(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    superseded = {
        str(record.get("supersedes_authorization_id"))
        for record in records
        if record.get("supersedes_authorization_id")
    }
    return [record for record in records if str(record.get("authorization_id")) not in superseded]


def verify_s2_authorizations(release_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        expected_candidate = _candidate_reference(release_dir)
        records = load_s2_authorizations(release_dir)
    except ObservatoryPublicationError as exc:
        return {"valid": False, "errors": [str(exc)], "record_count": 0, "active_count": 0}

    index: dict[str, dict[str, Any]] = {}
    for record in records:
        authorization_id = str(record.get("authorization_id") or "")
        if not authorization_id or authorization_id in index:
            errors.append("authorization IDs must be non-empty and unique")
            continue
        index[authorization_id] = record
        if record.get("authorization_sha256") != _digest_record(record, "authorization_sha256"):
            errors.append(f"{authorization_id}: authorization digest mismatch")
        if record.get("recorded_by") != DESIGNATED_OPERATOR:
            errors.append(f"{authorization_id}: wrong designated operator")
        if record.get("decision") not in {"AUTHORIZE", "WITHHOLD"}:
            errors.append(f"{authorization_id}: decision must be AUTHORIZE or WITHHOLD")
        if not str(record.get("decision_rationale") or "").strip():
            errors.append(f"{authorization_id}: decision rationale is required")
        if record.get("candidate_reference") != expected_candidate:
            errors.append(f"{authorization_id}: candidate binding mismatch")
        if record.get("boundary") != AUTHORIZATION_BOUNDARY:
            errors.append(f"{authorization_id}: authorization boundary mismatch")

    superseded_count: dict[str, int] = {}
    for record in records:
        prior_id = str(record.get("supersedes_authorization_id") or "")
        if not prior_id:
            continue
        superseded_count[prior_id] = superseded_count.get(prior_id, 0) + 1
        current_id = str(record.get("authorization_id") or "")
        prior = index.get(prior_id)
        if prior is None:
            errors.append(f"{current_id}: superseded authorization is missing")
        elif prior.get("candidate_reference") != record.get("candidate_reference"):
            errors.append(f"{current_id}: supersession changes candidate representation")
    if any(count != 1 for count in superseded_count.values()):
        errors.append("an authorization is superseded more than once")

    for start in index:
        seen: set[str] = set()
        current = start
        while current:
            if current in seen:
                errors.append("authorization supersession cycle detected")
                break
            seen.add(current)
            record = index.get(current)
            if record is None:
                break
            current = str(record.get("supersedes_authorization_id") or "")

    active = _active_authorizations(records)
    if len(active) > 1:
        errors.append("one exact S2 candidate has multiple active authorizations")

    publication = load_s2_publication(release_dir)
    if publication is not None:
        reference = publication.get("authorization_reference")
        published_id = str(reference.get("authorization_id") or "") if isinstance(reference, dict) else ""
        if published_id and published_id not in {str(record.get("authorization_id")) for record in active}:
            errors.append("published authorization is no longer active")

    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "record_count": len(records),
        "active_count": len(active),
    }


def record_s2_authorization(
    release_dir: Path,
    *,
    decision: str,
    decision_rationale: str,
    actor: str = DESIGNATED_OPERATOR,
    supersedes_authorization_id: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Record one explicit operator authorization decision over the exact S2 candidate."""
    if actor != DESIGNATED_OPERATOR:
        raise ObservatoryPublicationError(f"authorization actor must be {DESIGNATED_OPERATOR}")
    if decision not in {"AUTHORIZE", "WITHHOLD"} or not decision_rationale.strip():
        raise ObservatoryPublicationError("decision must be AUTHORIZE/WITHHOLD with a rationale")
    if verify_s2_authorizations(release_dir)["valid"] is not True:
        raise ObservatoryPublicationError("existing S2 authorization store is invalid")

    candidate_ref = _candidate_reference(release_dir)
    records = load_s2_authorizations(release_dir)
    active = _active_authorizations(records)
    publication = load_s2_publication(release_dir)
    if publication is not None:
        raise ObservatoryPublicationError("published S2 release is immutable; create a successor release")

    if supersedes_authorization_id is None:
        if active:
            raise ObservatoryPublicationError("exact S2 candidate already has an active authorization")
    else:
        if len(active) != 1 or active[0].get("authorization_id") != supersedes_authorization_id:
            raise ObservatoryPublicationError("supersession must target the active authorization")

    authorization_id = f"OBSAUTH-{uuid4().hex[:20].upper()}"
    record: dict[str, Any] = {
        "schema_version": "1",
        "authorization_id": authorization_id,
        "recorded_at": recorded_at or utc_now(),
        "recorded_by": actor,
        "candidate_reference": candidate_ref,
        "decision": decision,
        "decision_rationale": decision_rationale.strip(),
        "boundary": AUTHORIZATION_BOUNDARY,
    }
    if supersedes_authorization_id is not None:
        record["supersedes_authorization_id"] = supersedes_authorization_id
    record["authorization_sha256"] = _digest_record(record, "authorization_sha256")
    output = _authorization_root(release_dir) / f"{authorization_id}.json"
    atomic_write_json(output, record)

    report = verify_s2_authorizations(release_dir)
    if report["valid"] is not True:
        output.unlink(missing_ok=True)
        raise ObservatoryPublicationError(f"authorization failed verification: {report['errors']}")
    return {"authorization": record, "path": str(output)}


def record_s2_publication(
    release_dir: Path,
    *,
    publication_evidence: dict[str, str],
    actor: str = DESIGNATED_OPERATOR,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Bind one active AUTHORIZE record to explicit public publication evidence."""
    if actor != DESIGNATED_OPERATOR:
        raise ObservatoryPublicationError(f"publication actor must be {DESIGNATED_OPERATOR}")
    auth_report = verify_s2_authorizations(release_dir)
    if auth_report["valid"] is not True:
        raise ObservatoryPublicationError(f"authorization store is invalid: {auth_report['errors']}")
    if load_s2_publication(release_dir) is not None:
        raise ObservatoryPublicationError("S2 release already has a publication record")

    active = _active_authorizations(load_s2_authorizations(release_dir))
    if len(active) != 1 or active[0].get("decision") != "AUTHORIZE":
        raise ObservatoryPublicationError("publication requires exactly one active AUTHORIZE record")
    authorization = active[0]

    reference = str(publication_evidence.get("reference") or "").strip()
    if not reference.startswith("public-ref:") or reference == "public-ref:":
        raise ObservatoryPublicationError("publication evidence requires a non-empty public-ref:")
    evidence = {
        "reference": reference,
        "sha256": _require_hex(publication_evidence.get("sha256"), length=64, field="publication evidence sha256"),
    }
    candidate_ref = _candidate_reference(release_dir)
    publication_id = f"OBSPUB-{uuid4().hex[:20].upper()}"
    record: dict[str, Any] = {
        "schema_version": "1",
        "publication_id": publication_id,
        "recorded_at": recorded_at or utc_now(),
        "recorded_by": actor,
        "candidate_reference": candidate_ref,
        "authorization_reference": {
            "authorization_id": authorization["authorization_id"],
            "authorization_sha256": authorization["authorization_sha256"],
        },
        "publication_evidence": evidence,
        "automatic_publication_performed": False,
        "boundary": PUBLICATION_BOUNDARY,
    }
    record["publication_sha256"] = _digest_record(record, "publication_sha256")
    output = _governance_root(release_dir) / "publication.json"
    atomic_write_json(output, record)

    report = verify_s2_publication_binding(release_dir)
    if report["valid"] is not True:
        output.unlink(missing_ok=True)
        raise ObservatoryPublicationError(f"publication failed verification: {report['errors']}")
    return {"publication": record, "path": str(output)}


def verify_s2_publication_binding(release_dir: Path) -> dict[str, Any]:
    """Verify that one exact S2 candidate has active explicit authorization and publication."""
    errors: list[str] = []
    try:
        candidate_ref = _candidate_reference(release_dir)
    except ObservatoryPublicationError as exc:
        return {"valid": False, "errors": [str(exc)]}

    auth_report = verify_s2_authorizations(release_dir)
    errors.extend(auth_report["errors"])
    active = _active_authorizations(load_s2_authorizations(release_dir))
    publication = load_s2_publication(release_dir)
    if publication is None:
        errors.append("published S2 release requires governance/publication.json")
        return {"valid": False, "errors": sorted(set(errors))}
    if len(active) != 1:
        errors.append("published S2 release requires exactly one active authorization")
        return {"valid": False, "errors": sorted(set(errors))}
    authorization = active[0]
    if authorization.get("decision") != "AUTHORIZE":
        errors.append("active S2 authorization is not AUTHORIZE")

    publication_id = str(publication.get("publication_id") or "")
    if publication.get("publication_sha256") != _digest_record(publication, "publication_sha256"):
        errors.append(f"{publication_id}: publication digest mismatch")
    if publication.get("recorded_by") != DESIGNATED_OPERATOR:
        errors.append(f"{publication_id}: wrong publication operator")
    if publication.get("candidate_reference") != candidate_ref:
        errors.append(f"{publication_id}: publication candidate binding mismatch")
    expected_auth_ref = {
        "authorization_id": authorization.get("authorization_id"),
        "authorization_sha256": authorization.get("authorization_sha256"),
    }
    if publication.get("authorization_reference") != expected_auth_ref:
        errors.append(f"{publication_id}: publication authorization binding mismatch")
    if publication.get("automatic_publication_performed") is not False:
        errors.append(f"{publication_id}: automatic publication flag must remain false")
    if publication.get("boundary") != PUBLICATION_BOUNDARY:
        errors.append(f"{publication_id}: publication boundary mismatch")
    evidence = publication.get("publication_evidence")
    if not isinstance(evidence, dict):
        errors.append(f"{publication_id}: publication evidence is missing")
    else:
        reference = str(evidence.get("reference") or "")
        if not reference.startswith("public-ref:") or reference == "public-ref:":
            errors.append(f"{publication_id}: publication evidence reference is invalid")
        try:
            _require_hex(evidence.get("sha256"), length=64, field="publication evidence sha256")
        except ObservatoryPublicationError as exc:
            errors.append(f"{publication_id}: {exc}")

    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "candidate_id": candidate_ref["candidate_id"],
        "manifest_sha256": candidate_ref["manifest_sha256"],
        "authorization_id": authorization.get("authorization_id"),
        "authorization_sha256": authorization.get("authorization_sha256"),
        "publication_id": publication.get("publication_id"),
        "publication_sha256": publication.get("publication_sha256"),
    }
