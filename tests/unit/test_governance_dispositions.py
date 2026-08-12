from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.events import append_event, load_events
from neuroai_workbench.governance_dispositions import (
    CONDITION_REGISTER_BOUNDARY,
    OWNER_DISPOSITION_BOUNDARY,
    _condition_register_hash,
    _disposition_hash,
    _supersession_errors,
    load_governance_owner_dispositions,
    record_governance_owner_disposition,
    summarize_governance_owner_dispositions,
    verify_governance_owner_dispositions,
)
from neuroai_workbench.governance_opinions import (
    record_governance_reviewer_opinion,
    verify_governance_reviewer_opinions,
)
from neuroai_workbench.governance_scope import record_governance_scope_manifest, scope_object_for_path
from neuroai_workbench.util import atomic_write_json
from neuroai_workbench.workspace import Workspace


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace.initialize(tmp_path / "workspace")


def _scope(tmp_path: Path) -> tuple[Workspace, dict[str, object]]:
    workspace = _workspace(tmp_path)
    public = tmp_path / "public"
    generated = tmp_path / "generated"
    archive = tmp_path / "archive"
    for root in (public, generated, archive):
        root.mkdir()
    paths = {
        "predecessor": archive / "predecessor.json",
        "candidate": generated / "candidate.json",
        "delta": generated / "delta.json",
        "reopening": generated / "reopening.json",
        "products": generated / "products.json",
        "claims": public / "claims.json",
    }
    for name, path in paths.items():
        atomic_write_json(path, {"fixture": name})
    objects = [
        scope_object_for_path(
            role="PREDECESSOR_RELEASE",
            label="Predecessor",
            object_type="RELEASE",
            path=paths["predecessor"],
            storage_boundary="ARCHIVE",
            boundary_root=archive,
        ),
        scope_object_for_path(
            role="SUCCESSOR_CANDIDATE",
            label="Candidate",
            object_type="SUCCESSOR_CANDIDATE",
            path=paths["candidate"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="DELTA",
            label="Delta",
            object_type="DELTA",
            path=paths["delta"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="REOPENING_REGISTER",
            label="Reopening",
            object_type="REOPENING_REGISTER",
            path=paths["reopening"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="PRODUCT_MANIFEST",
            label="Products",
            object_type="PRODUCT_MANIFEST",
            path=paths["products"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="WITHHELD_CLAIMS",
            label="Claims",
            object_type="CLAIM_SET",
            path=paths["claims"],
            storage_boundary="PUBLIC_GIT",
            boundary_root=public,
        ),
    ]
    result = record_governance_scope_manifest(
        workspace,
        scope_label="Owner disposition fixture",
        objects=objects,
        boundary_roots={"PUBLIC_GIT": public, "GENERATED_OUTPUT": generated, "ARCHIVE": archive},
    )
    return workspace, result["manifest"]


def _claim(reviewer_key: str) -> dict[str, str]:
    return {
        "reviewer_key": reviewer_key,
        "name_or_role": f"Reviewer {reviewer_key}",
        "organization": "Example reviewer organization",
        "accountability_state": "CLAIMED_LOCAL_IDENTITY",
        "independence_statement": "No operational role in the reviewed implementation is claimed.",
        "conflict_of_interest_disclosure": "No conflict declared for this synthetic fixture.",
    }


def _owner(owner_key: str = "programme-owner") -> dict[str, str]:
    return {
        "owner_key": owner_key,
        "name_or_role": "Programme owner",
        "organization": "Example programme",
        "accountability_state": "CLAIMED_LOCAL_OWNER",
    }


def _opinion(
    workspace: Workspace,
    scope: dict[str, object],
    *,
    reviewer_key: str,
    track: str,
    state: str,
    conditions: list[str] | None = None,
    evidence_requests: list[str] | None = None,
    supersedes: str | None = None,
) -> dict[str, object]:
    return record_governance_reviewer_opinion(
        workspace,
        scope_id=str(scope["scope_id"]),
        scope_sha256=str(scope["manifest_sha256"]),
        review_track=track,
        opinion_state=state,
        reviewer_claim=_claim(reviewer_key),
        rationale=f"Synthetic {state} rationale.",
        conditions=conditions,
        evidence_requests=evidence_requests,
        supersedes_opinion_id=supersedes,
    )["opinion"]


def _condition(
    *,
    condition_id: str | None = None,
    status: str = "OPEN",
    release_effect: str = "BLOCKS_RELEASE",
    closure: dict[str, object] | None = None,
    description: str = "Publish the missing methodology appendix.",
    owner: str = "programme-owner",
    priority: str = "HIGH",
) -> dict[str, object]:
    value: dict[str, object] = {
        "description": description,
        "owner": owner,
        "priority": priority,
        "status": status,
        "release_effect": release_effect,
        "closure_evidence_reference": closure,
    }
    if condition_id is not None:
        value["condition_id"] = condition_id
    return value


def _dispose(
    workspace: Workspace,
    scope: dict[str, object],
    opinions: list[dict[str, object]],
    *,
    state: str = "ACCEPT",
    conditions: list[dict[str, object]] | None = None,
    supersedes: str | None = None,
) -> dict[str, object]:
    return record_governance_owner_disposition(
        workspace,
        scope_id=str(scope["scope_id"]),
        scope_sha256=str(scope["manifest_sha256"]),
        opinion_ids=[str(item["opinion_id"]) for item in opinions],
        disposition_state=state,
        owner_claim=_owner(),
        rationale=f"Synthetic owner disposition: {state}.",
        conditions=conditions,
        supersedes_disposition_id=supersedes,
    )["disposition"]


def test_record_verify_and_summarize_owner_disposition(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    opinion = _opinion(workspace, scope, reviewer_key="reviewer-a", track="SECURITY", state="SUPPORT")
    disposition = _dispose(workspace, scope, [opinion])

    register = disposition["condition_register"]
    assert disposition["disposition_sha256"] == _disposition_hash(disposition)
    assert register["register_sha256"] == _condition_register_hash(register)
    assert disposition["boundary"] == OWNER_DISPOSITION_BOUNDARY
    assert register["boundary"] == CONDITION_REGISTER_BOUNDARY
    assert disposition["release_authorization_performed"] is False

    verification = verify_governance_owner_dispositions(workspace)
    assert verification["valid"] is True
    assert verification["counts"]["dispositions"] == 1
    assert verification["counts"]["unaddressed_active_opinions"] == 0
    assert verification["event_chain_valid"] is True

    summary = summarize_governance_owner_dispositions(workspace)
    assert summary["integrity_valid"] is True
    assert summary["owner_disposition_complete"] is True
    assert summary["release_readiness_established"] is False
    assert summary["release_authorization_performed"] is False

    event = load_events(workspace.root / "events.jsonl")[-1]
    assert event["action"] == "GOVERNANCE_OWNER_DISPOSITION_RECORDED"
    assert event["payload"]["disposition_sha256"] == disposition["disposition_sha256"]
    assert event["payload"]["condition_register_sha256"] == register["register_sha256"]


def test_partial_disposition_preserves_unaddressed_states(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    support = _opinion(workspace, scope, reviewer_key="supporter", track="SECURITY", state="SUPPORT")
    objection = _opinion(workspace, scope, reviewer_key="objector", track="SECURITY", state="OBJECT")
    abstain = _opinion(workspace, scope, reviewer_key="abstainer", track="METHODOLOGY", state="ABSTAIN")
    request = _opinion(
        workspace,
        scope,
        reviewer_key="requester",
        track="DATA_GOVERNANCE",
        state="REQUEST_EVIDENCE",
        evidence_requests=["Provide retention evidence."],
    )

    _dispose(workspace, scope, [support])
    summary = summarize_governance_owner_dispositions(workspace)
    assert summary["owner_disposition_complete"] is False
    assert summary["unaddressed_objection_present"] is True
    assert summary["unaddressed_abstention_present"] is True
    assert summary["unaddressed_evidence_request_present"] is True
    assert {item["opinion_id"] for item in summary["unaddressed_active_opinions"]} == {
        objection["opinion_id"],
        abstain["opinion_id"],
        request["opinion_id"],
    }


def test_overlapping_active_disposition_is_refused(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    opinion = _opinion(workspace, scope, reviewer_key="reviewer-a", track="SECURITY", state="OBJECT")
    _dispose(workspace, scope, [opinion], state="DEFER")
    with pytest.raises(ValueError, match="already addresses opinion IDs"):
        _dispose(workspace, scope, [opinion], state="REQUEST_FURTHER_REVIEW")


def test_supersession_preserves_history_and_exact_opinion_set(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    opinion = _opinion(workspace, scope, reviewer_key="reviewer-a", track="SECURITY", state="OBJECT")
    first = _dispose(workspace, scope, [opinion], state="DEFER")
    second = _dispose(
        workspace,
        scope,
        [opinion],
        state="REJECT",
        supersedes=str(first["disposition_id"]),
    )

    records = load_governance_owner_dispositions(workspace)
    assert len(records) == 2
    assert second["supersedes_disposition_id"] == first["disposition_id"]
    assert second["supersedes_disposition_sha256"] == first["disposition_sha256"]
    assert second["condition_register"]["supersedes_register_id"] == first["condition_register"]["register_id"]
    assert verify_governance_owner_dispositions(workspace)["valid"] is True

    other = _opinion(workspace, scope, reviewer_key="reviewer-b", track="METHODOLOGY", state="SUPPORT")
    with pytest.raises(ValueError, match="exact predecessor opinion set"):
        _dispose(
            workspace,
            scope,
            [opinion, other],
            supersedes=str(second["disposition_id"]),
        )


def test_accept_with_action_requires_condition(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    opinion = _opinion(workspace, scope, reviewer_key="reviewer-a", track="SECURITY", state="SUPPORT")
    with pytest.raises(ValueError, match="requires at least one condition"):
        _dispose(workspace, scope, [opinion], state="ACCEPT_WITH_ACTION")


def test_blocking_condition_remains_explicit(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    opinion = _opinion(
        workspace,
        scope,
        reviewer_key="reviewer-a",
        track="METHODOLOGY",
        state="SUPPORT_WITH_CONDITIONS",
        conditions=["Publish methodology appendix."],
    )
    disposition = _dispose(
        workspace,
        scope,
        [opinion],
        state="ACCEPT_WITH_ACTION",
        conditions=[_condition()],
    )
    condition = disposition["condition_register"]["conditions"][0]
    assert condition["status"] == "OPEN"
    assert condition["release_effect"] == "BLOCKS_RELEASE"

    summary = summarize_governance_owner_dispositions(workspace)
    assert summary["release_blocking_condition_present"] is True
    assert [item["condition_id"] for item in summary["release_blocking_conditions"]] == [condition["condition_id"]]
    assert summary["release_readiness_established"] is False


def test_condition_resolution_requires_and_preserves_closure_evidence(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    opinion = _opinion(workspace, scope, reviewer_key="reviewer-a", track="METHODOLOGY", state="OBJECT")
    first = _dispose(
        workspace,
        scope,
        [opinion],
        state="ACCEPT_WITH_ACTION",
        conditions=[_condition()],
    )
    condition = first["condition_register"]["conditions"][0]
    condition_id = str(condition["condition_id"])

    with pytest.raises(ValueError, match="require closure_evidence_reference"):
        _dispose(
            workspace,
            scope,
            [opinion],
            state="ACCEPT_WITH_ACTION",
            conditions=[_condition(condition_id=condition_id, status="RESOLVED")],
            supersedes=str(first["disposition_id"]),
        )

    closure = {
        "label": "Protected closure receipt",
        "sha256": "c" * 64,
        "storage_boundary": "PROTECTED_WORKSPACE",
        "locator": "protected-ref:condition-closure-receipt",
    }
    second = _dispose(
        workspace,
        scope,
        [opinion],
        state="ACCEPT",
        conditions=[_condition(condition_id=condition_id, status="RESOLVED", closure=closure)],
        supersedes=str(first["disposition_id"]),
    )
    resolved = second["condition_register"]["conditions"][0]
    assert resolved["condition_id"] == condition_id
    assert resolved["closure_evidence_reference"] == closure
    summary = summarize_governance_owner_dispositions(workspace)
    assert summary["release_blocking_condition_present"] is False
    assert summary["unresolved_conditions"] == []


def test_unresolved_condition_cannot_claim_closure_evidence(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    opinion = _opinion(workspace, scope, reviewer_key="reviewer-a", track="SECURITY", state="OBJECT")
    closure = {
        "label": "Receipt",
        "sha256": "d" * 64,
        "storage_boundary": "PUBLIC_GIT",
        "locator": "receipts/closure.json",
    }
    with pytest.raises(ValueError, match="Only RESOLVED"):
        _dispose(
            workspace,
            scope,
            [opinion],
            state="ACCEPT_WITH_ACTION",
            conditions=[_condition(closure=closure)],
        )


def test_condition_core_fields_are_immutable_across_supersession(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    opinion = _opinion(workspace, scope, reviewer_key="reviewer-a", track="SECURITY", state="OBJECT")
    first = _dispose(
        workspace,
        scope,
        [opinion],
        state="ACCEPT_WITH_ACTION",
        conditions=[_condition()],
    )
    condition_id = str(first["condition_register"]["conditions"][0]["condition_id"])
    with pytest.raises(ValueError, match="changes immutable field owner"):
        _dispose(
            workspace,
            scope,
            [opinion],
            state="ACCEPT_WITH_ACTION",
            conditions=[_condition(condition_id=condition_id, owner="different-owner")],
            supersedes=str(first["disposition_id"]),
        )


def test_prior_conditions_cannot_silently_disappear(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    opinion = _opinion(workspace, scope, reviewer_key="reviewer-a", track="SECURITY", state="OBJECT")
    first = _dispose(
        workspace,
        scope,
        [opinion],
        state="ACCEPT_WITH_ACTION",
        conditions=[_condition()],
    )
    second = _dispose(
        workspace,
        scope,
        [opinion],
        state="DEFER",
        supersedes=str(first["disposition_id"]),
    )
    assert second["condition_register"]["conditions"] == first["condition_register"]["conditions"]


def test_superseded_reviewer_opinion_cannot_be_dispositioned(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    first = _opinion(workspace, scope, reviewer_key="reviewer-a", track="SECURITY", state="SUPPORT")
    second = _opinion(
        workspace,
        scope,
        reviewer_key="reviewer-a",
        track="SECURITY",
        state="OBJECT",
        supersedes=str(first["opinion_id"]),
    )
    assert verify_governance_reviewer_opinions(workspace)["valid"] is True
    with pytest.raises(ValueError, match="not the current active opinion"):
        _dispose(workspace, scope, [first], state="ACCEPT")
    _dispose(workspace, scope, [second], state="DEFER")


def test_invalid_inputs_fail_closed(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    opinion = _opinion(workspace, scope, reviewer_key="reviewer-a", track="SECURITY", state="SUPPORT")
    base = {
        "workspace": workspace,
        "scope_id": str(scope["scope_id"]),
        "scope_sha256": str(scope["manifest_sha256"]),
        "opinion_ids": [str(opinion["opinion_id"])],
        "disposition_state": "ACCEPT",
        "owner_claim": _owner(),
        "rationale": "Valid rationale.",
    }
    with pytest.raises(ValueError, match="Unsupported owner disposition state"):
        record_governance_owner_disposition(**{**base, "disposition_state": "GO"})
    with pytest.raises(ValueError, match="rationale must not be empty"):
        record_governance_owner_disposition(**{**base, "rationale": " "})
    with pytest.raises(ValueError, match="Duplicate opinion IDs"):
        record_governance_owner_disposition(**{**base, "opinion_ids": base["opinion_ids"] * 2})
    with pytest.raises(ValueError, match="owner_claim.name_or_role is required"):
        record_governance_owner_disposition(
            **{**base, "owner_claim": {"owner_key": "owner", "accountability_state": "CLAIMED"}}
        )


def test_invalid_closure_locator_is_refused(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    opinion = _opinion(workspace, scope, reviewer_key="reviewer-a", track="SECURITY", state="OBJECT")
    with pytest.raises(ValueError, match="normalized relative POSIX path"):
        _dispose(
            workspace,
            scope,
            [opinion],
            state="ACCEPT_WITH_ACTION",
            conditions=[
                _condition(
                    status="RESOLVED",
                    closure={
                        "label": "Bad closure",
                        "sha256": "e" * 64,
                        "storage_boundary": "PUBLIC_GIT",
                        "locator": "../escape.json",
                    },
                )
            ],
        )


def test_tampered_disposition_and_condition_register_are_detected(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    opinion = _opinion(workspace, scope, reviewer_key="reviewer-a", track="SECURITY", state="OBJECT")
    disposition = _dispose(
        workspace,
        scope,
        [opinion],
        state="ACCEPT_WITH_ACTION",
        conditions=[_condition()],
    )
    path = Path(load_governance_owner_dispositions(workspace)[0]["_path"])
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored["rationale"] = "Tampered rationale"
    atomic_write_json(path, stored)
    verification = verify_governance_owner_dispositions(workspace)
    assert verification["valid"] is False
    assert any("hash mismatch" in error for error in verification["errors"])

    stored = dict(disposition)
    stored["condition_register"] = dict(disposition["condition_register"])
    stored["condition_register"]["boundary"] = "tampered"
    stored["condition_register"]["register_sha256"] = _condition_register_hash(stored["condition_register"])
    stored["disposition_sha256"] = _disposition_hash(stored)
    atomic_write_json(path, stored)
    verification = verify_governance_owner_dispositions(workspace)
    assert verification["valid"] is False
    assert any("condition register boundary mismatch" in error for error in verification["errors"])


def test_missing_or_duplicate_event_binding_is_detected(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    opinion = _opinion(workspace, scope, reviewer_key="reviewer-a", track="SECURITY", state="SUPPORT")
    disposition = _dispose(workspace, scope, [opinion])
    register = disposition["condition_register"]

    events_path = workspace.root / "events.jsonl"
    events = load_events(events_path)
    owner_events = [event for event in events if event["action"] == "GOVERNANCE_OWNER_DISPOSITION_RECORDED"]
    assert len(owner_events) == 1

    append_event(
        events_path,
        "GOVERNANCE_OWNER_DISPOSITION_RECORDED",
        "local-user",
        {
            "disposition_id": disposition["disposition_id"],
            "disposition_sha256": disposition["disposition_sha256"],
            "condition_register_id": register["register_id"],
            "condition_register_sha256": register["register_sha256"],
            "scope_id": scope["scope_id"],
            "scope_sha256": scope["manifest_sha256"],
            "release_authorization_performed": False,
        },
    )
    verification = verify_governance_owner_dispositions(workspace)
    assert verification["valid"] is False
    assert any("matching append-only events" in error for error in verification["errors"])


def test_overlapping_active_records_introduced_by_tampering_are_detected(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    opinion = _opinion(workspace, scope, reviewer_key="reviewer-a", track="SECURITY", state="SUPPORT")
    first = _dispose(workspace, scope, [opinion])
    original = json.loads(Path(load_governance_owner_dispositions(workspace)[0]["_path"]).read_text(encoding="utf-8"))
    duplicate = dict(original)
    duplicate["disposition_id"] = "GOVDISP-" + "f" * 32
    duplicate["condition_register"] = dict(original["condition_register"])
    duplicate["condition_register"]["register_id"] = "GOVCONDREG-" + "e" * 32
    duplicate["condition_register"]["disposition_id"] = duplicate["disposition_id"]
    duplicate["condition_register"]["register_sha256"] = _condition_register_hash(duplicate["condition_register"])
    duplicate["disposition_sha256"] = _disposition_hash(duplicate)
    path = workspace.root / "governance" / "owner-dispositions" / f"{duplicate['disposition_id']}.json"
    atomic_write_json(path, duplicate)
    append_event(
        workspace.root / "events.jsonl",
        "GOVERNANCE_OWNER_DISPOSITION_RECORDED",
        "local-user",
        {
            "disposition_id": duplicate["disposition_id"],
            "disposition_sha256": duplicate["disposition_sha256"],
            "condition_register_id": duplicate["condition_register"]["register_id"],
            "condition_register_sha256": duplicate["condition_register"]["register_sha256"],
            "scope_id": duplicate["scope_id"],
            "scope_sha256": duplicate["scope_sha256"],
            "release_authorization_performed": False,
        },
    )
    verification = verify_governance_owner_dispositions(workspace)
    assert verification["valid"] is False
    assert any("addressed by 2 active owner dispositions" in error for error in verification["errors"])
    assert first["disposition_id"] != duplicate["disposition_id"]


def test_supersession_error_helper_detects_branch_and_cycle() -> None:
    base = {
        "scope_id": "GOVSCOPE-" + "1" * 32,
        "scope_sha256": "a" * 64,
        "addressed_opinions": [{"opinion_id": "GOVOP-" + "2" * 32, "opinion_sha256": "b" * 64}],
        "condition_register": {
            "register_id": "GOVCONDREG-" + "3" * 32,
            "register_sha256": "c" * 64,
            "conditions": [],
        },
    }
    first = {
        **base,
        "disposition_id": "GOVDISP-" + "4" * 32,
        "disposition_sha256": "d" * 64,
    }
    second = {
        **base,
        "disposition_id": "GOVDISP-" + "5" * 32,
        "disposition_sha256": "e" * 64,
        "supersedes_disposition_id": first["disposition_id"],
        "supersedes_disposition_sha256": first["disposition_sha256"],
        "condition_register": {
            **base["condition_register"],
            "register_id": "GOVCONDREG-" + "6" * 32,
            "supersedes_register_id": base["condition_register"]["register_id"],
            "supersedes_register_sha256": base["condition_register"]["register_sha256"],
        },
    }
    third = {
        **second,
        "disposition_id": "GOVDISP-" + "7" * 32,
        "disposition_sha256": "f" * 64,
    }
    errors = _supersession_errors([first, second, third])
    assert any("branching supersession" in error for error in errors)

    first["supersedes_disposition_id"] = second["disposition_id"]
    first["supersedes_disposition_sha256"] = second["disposition_sha256"]
    errors = _supersession_errors([first, second])
    assert any("cycle detected" in error for error in errors)


def test_invalid_underlying_opinion_store_blocks_new_disposition(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    opinion = _opinion(workspace, scope, reviewer_key="reviewer-a", track="SECURITY", state="SUPPORT")
    opinion_path = next((workspace.root / "governance" / "opinions").glob("*.json"))
    stored = json.loads(opinion_path.read_text(encoding="utf-8"))
    stored["rationale"] = "tampered"
    atomic_write_json(opinion_path, stored)
    with pytest.raises(ValueError, match="opinion store failed verification"):
        _dispose(workspace, scope, [opinion])
