from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

from .governance_dispositions import record_governance_owner_disposition
from .governance_opinions import REVIEW_TRACKS, record_governance_reviewer_opinion
from .governance_policy import evaluate_governance_completion
from .governance_release import (
    _normalize_authority_claim,
    build_release_readiness_package,
)
from .util import atomic_write_json, canonical_json_bytes, sha256_bytes, utc_now
from .workspace import Workspace

REHEARSAL_EXECUTION_MODE = "SYNTHETIC_REHEARSAL"
SYNTHETIC_REVIEWER_STATE = "SYNTHETIC_REHEARSAL_REVIEWER"
SYNTHETIC_OWNER_STATE = "SYNTHETIC_REHEARSAL_OWNER"
REHEARSAL_BOUNDARY = (
    "Synthetic governance rehearsal exercises workflow mechanics only. It does not represent real reviewers or owners, "
    "authenticate identities, establish independence, institutional delegation, scientific or regulatory approval, "
    "release authority, canonical successor authorization, publication authority, or UNESCO endorsement."
)

TRACK_QUESTIONS: dict[str, tuple[str, ...]] = {
    "SECURITY": (
        "Are security assumptions, attack surfaces, privileged transitions, and unresolved security conditions explicit?",
        "Do release controls fail closed under tampering, concurrency, interruption, and stale-input substitution?",
    ),
    "METHODOLOGY": (
        "Are assessment methods, evidence dependencies, uncertainty states, and reopening semantics inspectable?",
        "Do reported conclusions remain within the evidential scope of the reviewed artifacts?",
    ),
    "DATA_GOVERNANCE": (
        "Are provenance, licensing, protected/public boundaries, retention, and disclosure constraints explicit?",
        "Can every release input be traced to an exact digest without exposing protected evidence?",
    ),
    "ACCESSIBILITY": (
        "Are public products usable and interpretable across the programme's intended accessibility requirements?",
        "Are known accessibility gaps recorded as explicit conditions rather than silently omitted?",
    ),
    "DOMAIN": (
        "Do domain-specific interpretations preserve distinctions among research, regulatory, clinical, and deployment states?",
        "Are unresolved domain questions and evidence gaps visible to the release decision?",
    ),
    "AFFECTED_COMMUNITY": (
        "Are affected-community perspectives represented as an explicit governance track with visible gaps and dissent?",
        "Can abstention, objection, requested evidence, and minority positions remain visible without being converted to support?",
    ),
}


def _synthetic_reviewer_claim(track: str, key: str) -> dict[str, str]:
    return {
        "reviewer_key": key,
        "name_or_role": f"TEST FIXTURE ONLY synthetic {track.lower()} reviewer",
        "organization": "TEST FIXTURE ONLY synthetic rehearsal",
        "accountability_state": SYNTHETIC_REVIEWER_STATE,
        "independence_statement": "TEST FIXTURE ONLY; synthetic rehearsal claim, not a real-world independence assertion.",
        "conflict_of_interest_disclosure": "TEST FIXTURE ONLY; no real conflict-of-interest statement is made.",
    }


def _synthetic_owner_claim() -> dict[str, str]:
    return {
        "owner_key": "synthetic-rehearsal-owner",
        "name_or_role": "TEST FIXTURE ONLY synthetic rehearsal owner",
        "organization": "TEST FIXTURE ONLY synthetic rehearsal",
        "accountability_state": SYNTHETIC_OWNER_STATE,
        "accountability_statement": "TEST FIXTURE ONLY; no institutional delegation or release authority is asserted.",
    }


def _record_opinion(
    workspace: Workspace,
    *,
    scope_id: str,
    scope_sha256: str,
    track: str,
    state: str,
    reviewer_key: str,
    supersedes_opinion_id: str | None = None,
) -> dict[str, Any]:
    result = record_governance_reviewer_opinion(
        workspace,
        scope_id=scope_id,
        scope_sha256=scope_sha256,
        review_track=track,
        opinion_state=state,
        reviewer_claim=_synthetic_reviewer_claim(track, reviewer_key),
        rationale=f"TEST FIXTURE ONLY synthetic {state} opinion for governance rehearsal.",
        conditions=(
            ["TEST FIXTURE ONLY: retain the synthetic domain condition for rehearsal."]
            if state == "SUPPORT_WITH_CONDITIONS"
            else []
        ),
        evidence_requests=(
            ["TEST FIXTURE ONLY: supply additional evidence for the rehearsal branch."]
            if state == "REQUEST_EVIDENCE"
            else []
        ),
        supersedes_opinion_id=supersedes_opinion_id,
        actor="synthetic-rehearsal",
    )
    return cast(dict[str, Any], result["opinion"])


def _record_fixture_opinions(
    workspace: Workspace,
    *,
    scope_id: str,
    scope_sha256: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    security_initial = _record_opinion(
        workspace,
        scope_id=scope_id,
        scope_sha256=scope_sha256,
        track="SECURITY",
        state="SUPPORT",
        reviewer_key="synthetic-security-a",
    )
    records.append(security_initial)
    records.append(
        _record_opinion(
            workspace,
            scope_id=scope_id,
            scope_sha256=scope_sha256,
            track="SECURITY",
            state="OBJECT",
            reviewer_key="synthetic-security-a",
            supersedes_opinion_id=str(security_initial["opinion_id"]),
        )
    )
    fixture_states = {
        "METHODOLOGY": "SUPPORT",
        "DATA_GOVERNANCE": "REQUEST_EVIDENCE",
        "ACCESSIBILITY": "ABSTAIN",
        "DOMAIN": "SUPPORT_WITH_CONDITIONS",
        "AFFECTED_COMMUNITY": "SUPPORT",
    }
    for track, state in fixture_states.items():
        records.append(
            _record_opinion(
                workspace,
                scope_id=scope_id,
                scope_sha256=scope_sha256,
                track=track,
                state=state,
                reviewer_key=f"synthetic-{track.lower()}-a",
            )
        )
    return records


def _active_fixture(records: list[dict[str, Any]], *, track: str) -> dict[str, Any]:
    track_records = [record for record in records if record.get("review_track") == track]
    superseded = {
        str(record.get("supersedes_opinion_id")) for record in track_records if record.get("supersedes_opinion_id")
    }
    active = [record for record in track_records if str(record.get("opinion_id")) not in superseded]
    if len(active) != 1:
        raise ValueError(f"Synthetic rehearsal expected one active opinion for {track}, found {len(active)}")
    return active[0]


def _record_fixture_dispositions(
    workspace: Workspace,
    *,
    scope_id: str,
    scope_sha256: str,
    opinions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    owner = _synthetic_owner_claim()
    security = _active_fixture(opinions, track="SECURITY")
    data = _active_fixture(opinions, track="DATA_GOVERNANCE")
    domain = _active_fixture(opinions, track="DOMAIN")

    dispositions = [
        record_governance_owner_disposition(
            workspace,
            scope_id=scope_id,
            scope_sha256=scope_sha256,
            opinion_ids=[str(security["opinion_id"])],
            disposition_state="DEFER",
            owner_claim=owner,
            rationale="TEST FIXTURE ONLY: synthetic objection remains unresolved.",
            actor="synthetic-rehearsal",
        )["disposition"],
        record_governance_owner_disposition(
            workspace,
            scope_id=scope_id,
            scope_sha256=scope_sha256,
            opinion_ids=[str(data["opinion_id"])],
            disposition_state="REQUEST_FURTHER_REVIEW",
            owner_claim=owner,
            rationale="TEST FIXTURE ONLY: synthetic evidence request remains open.",
            actor="synthetic-rehearsal",
        )["disposition"],
        record_governance_owner_disposition(
            workspace,
            scope_id=scope_id,
            scope_sha256=scope_sha256,
            opinion_ids=[str(domain["opinion_id"])],
            disposition_state="ACCEPT_WITH_ACTION",
            owner_claim=owner,
            rationale="TEST FIXTURE ONLY: synthetic domain condition is tracked as release-blocking.",
            conditions=[
                {
                    "condition_id": "GOVCOND-00000000000000000000000000000001",
                    "description": "TEST FIXTURE ONLY unresolved domain action for rehearsal.",
                    "owner": "synthetic-rehearsal-owner",
                    "priority": "HIGH",
                    "status": "OPEN",
                    "release_effect": "BLOCKS_RELEASE",
                }
            ],
            actor="synthetic-rehearsal",
        )["disposition"],
    ]
    return dispositions


def _synthetic_authority_probe() -> dict[str, Any]:
    claim = {
        "name_or_role": "TEST FIXTURE ONLY synthetic release authority",
        "organization": "TEST FIXTURE ONLY synthetic rehearsal",
        "authority_basis": "TEST FIXTURE ONLY authority-escalation probe",
        "accountability_state": "CLAIMED_EXTERNAL_RELEASE_AUTHORITY",
        "execution_mode": REHEARSAL_EXECUTION_MODE,
        "authority_evidence_reference": "protected-ref:test-fixture-only/synthetic-authority",
        "authority_evidence_sha256": "0" * 64,
    }
    try:
        _normalize_authority_claim(claim)
    except ValueError as exc:
        return {
            "attempted": True,
            "blocked": True,
            "error": str(exc),
            "authorization_created": False,
        }
    raise AssertionError("Synthetic rehearsal authority probe unexpectedly passed")


def build_handoff_template(
    *,
    scope_id: str,
    scope_sha256: str,
    candidate_reference: dict[str, Any],
    policy_evaluation_reference: dict[str, Any],
    readiness_package_reference: dict[str, Any],
) -> dict[str, Any]:
    tracks = [
        {
            "track": track,
            "questions": list(TRACK_QUESTIONS[track]),
            "required_return_record": "GOVERNANCE_REVIEWER_OPINION.schema.json",
            "identity_placeholder": "<REAL_REVIEWER_TO_BE_SUPPLIED_OUTSIDE_SYNTHETIC_REHEARSAL>",
        }
        for track in sorted(REVIEW_TRACKS)
    ]
    template: dict[str, Any] = {
        "schema_version": "1",
        "handoff_state": "TEMPLATE_ONLY_REAL_HUMAN_EXECUTION_DEFERRED",
        "scope_reference": {"scope_id": scope_id, "scope_sha256": scope_sha256},
        "candidate_reference": candidate_reference,
        "policy_evaluation_reference": policy_evaluation_reference,
        "readiness_package_reference": readiness_package_reference,
        "tracks": tracks,
        "schemas": [
            "GOVERNANCE_REVIEWER_OPINION.schema.json",
            "GOVERNANCE_OWNER_DISPOSITION.schema.json",
            "GOVERNANCE_RELEASE_DECISION.schema.json",
        ],
        "verification_commands": [
            "python -m pytest tests/unit/test_governance_scope.py tests/unit/test_governance_opinions.py",
            "python -m pytest tests/unit/test_governance_dispositions.py tests/unit/test_governance_policy.py",
            "python -m pytest tests/unit/test_governance_release.py tests/unit/test_governance_release_adversarial.py",
        ],
        "return_instructions": [
            "Return reviewer records only through the protected governance workflow; do not commit protected evidence bytes.",
            "Bind every returned record to the exact scope ID/SHA and reviewed artifact digests supplied in this handoff.",
            "Preserve objections, abstentions, evidence requests, minority views, and unresolved conditions without rewriting prior records.",
            "Do not create an AUTHORIZED or PUBLISHED decision until real release-authority evidence is supplied through the protected workflow.",
        ],
        "protected_evidence_included": False,
        "real_reviewer_records_included": False,
        "real_owner_dispositions_included": False,
        "real_release_authority_decision_included": False,
        "canonical_publication_authorized": False,
        "boundary": REHEARSAL_BOUNDARY,
    }
    template["template_sha256"] = sha256_bytes(canonical_json_bytes(template))
    return template


def run_synthetic_governance_rehearsal(
    workspace: Workspace,
    *,
    scope_id: str,
    scope_sha256: str,
    candidate: dict[str, Any],
    products: list[dict[str, str]],
) -> dict[str, Any]:
    """Exercise the governance stack with synthetic claims and emit a non-authoritative certificate."""
    opinions = _record_fixture_opinions(
        workspace,
        scope_id=scope_id,
        scope_sha256=scope_sha256,
    )
    dispositions = _record_fixture_dispositions(
        workspace,
        scope_id=scope_id,
        scope_sha256=scope_sha256,
        opinions=opinions,
    )
    evaluation = evaluate_governance_completion(
        workspace,
        scope_id=scope_id,
        scope_sha256=scope_sha256,
    )
    readiness = build_release_readiness_package(
        workspace,
        candidate=candidate,
        scope_id=scope_id,
        scope_sha256=scope_sha256,
        products=products,
    )
    authority_probe = _synthetic_authority_probe()
    if readiness.get("readiness_state") == "READY_FOR_REAL_AUTHORITY_REVIEW":
        raise AssertionError("Synthetic rehearsal unexpectedly satisfied real-authority readiness")
    if not authority_probe["blocked"]:
        raise AssertionError("Synthetic rehearsal unexpectedly passed the authority boundary")

    certificate: dict[str, Any] = {
        "schema_version": "1",
        "certificate_id": f"GOVREHEARSAL-{uuid4().hex[:16].upper()}",
        "generated_at": utc_now(),
        "execution_mode": REHEARSAL_EXECUTION_MODE,
        "authoritative": False,
        "scope_reference": {"scope_id": scope_id, "scope_sha256": scope_sha256},
        "synthetic_opinion_records": [
            {"opinion_id": str(item["opinion_id"]), "opinion_sha256": str(item["opinion_sha256"])} for item in opinions
        ],
        "synthetic_disposition_records": [
            {
                "disposition_id": str(item["disposition_id"]),
                "disposition_sha256": str(item["disposition_sha256"]),
                "condition_register_sha256": str(item["condition_register"]["register_sha256"]),
            }
            for item in dispositions
        ],
        "policy_evaluation_reference": {
            "evaluation_id": str(evaluation["evaluation_id"]),
            "evaluation_sha256": str(evaluation["evaluation_sha256"]),
            "input_binding_sha256": str(evaluation["input_binding_sha256"]),
            "release_readiness": str(evaluation["release_readiness"]),
        },
        "release_readiness_package_reference": {
            "package_id": str(readiness["package_id"]),
            "package_sha256": str(readiness["package_sha256"]),
            "readiness_state": str(readiness["readiness_state"]),
            "blocker_codes": list(readiness["blocker_codes"]),
        },
        "authority_boundary_probe": authority_probe,
        "release_authorization_performed": False,
        "canonical_successor_authorized": False,
        "publication_authorized": False,
        "real_human_governance_completed": False,
        "required_real_human_actions": [
            "REAL_REVIEWER_RECORDS_PENDING",
            "REAL_OWNER_DISPOSITIONS_PENDING",
            "REAL_RELEASE_AUTHORITY_DECISION_PENDING",
            "CANONICAL_PUBLICATION_PENDING",
        ],
        "boundary": REHEARSAL_BOUNDARY,
    }
    handoff = build_handoff_template(
        scope_id=scope_id,
        scope_sha256=scope_sha256,
        candidate_reference=dict(readiness["candidate_reference"]),
        policy_evaluation_reference=dict(readiness["policy_evaluation_reference"]),
        readiness_package_reference={
            "package_id": str(readiness["package_id"]),
            "package_sha256": str(readiness["package_sha256"]),
        },
    )
    certificate["handoff_template_sha256"] = handoff["template_sha256"]
    certificate["certificate_sha256"] = sha256_bytes(canonical_json_bytes(certificate))

    root = workspace.root / "governance" / "rehearsal"
    root.mkdir(parents=True, exist_ok=True)
    certificate_path = root / f"{certificate['certificate_id']}.json"
    handoff_path = root / f"{certificate['certificate_id']}.handoff-template.json"
    atomic_write_json(certificate_path, certificate)
    atomic_write_json(handoff_path, handoff)
    return {
        "certificate": certificate,
        "handoff_template": handoff,
        "certificate_path": str(certificate_path),
        "handoff_template_path": str(handoff_path),
    }
