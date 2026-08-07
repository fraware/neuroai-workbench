from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import neuroai_workbench.governance_dispositions as gd
from neuroai_workbench.util import atomic_write_json
from neuroai_workbench.workspace import Workspace


VALID_SCOPE_ID = "GOVSCOPE-" + "1" * 32
VALID_SCOPE_SHA = "a" * 64
VALID_OPINION_ID = "GOVOP-" + "2" * 32
VALID_OPINION_SHA = "b" * 64
VALID_DISPOSITION_ID = "GOVDISP-" + "3" * 32
VALID_DISPOSITION_SHA = "c" * 64
VALID_REGISTER_ID = "GOVCONDREG-" + "4" * 32
VALID_REGISTER_SHA = "d" * 64
VALID_CONDITION_ID = "GOVCOND-" + "5" * 32


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace.initialize(tmp_path / "workspace")


def _opinion(
    *,
    opinion_id: str = VALID_OPINION_ID,
    opinion_sha: str = VALID_OPINION_SHA,
    scope_id: str = VALID_SCOPE_ID,
    scope_sha: str = VALID_SCOPE_SHA,
    reviewer: Any = None,
) -> dict[str, Any]:
    if reviewer is None:
        reviewer = {"reviewer_key": "reviewer-a"}
    return {
        "opinion_id": opinion_id,
        "opinion_sha256": opinion_sha,
        "scope_id": scope_id,
        "scope_sha256": scope_sha,
        "review_track": "SECURITY",
        "opinion_state": "OBJECT",
        "reviewer_claim": reviewer,
    }


def _owner() -> dict[str, str]:
    return {
        "owner_key": "programme-owner",
        "name_or_role": "Programme owner",
        "organization": "Example programme",
        "accountability_state": "CLAIMED_LOCAL_OWNER",
    }


def _condition(
    *,
    condition_id: str = VALID_CONDITION_ID,
    description: str = "Resolve the blocker.",
    owner: str = "programme-owner",
    priority: str = "HIGH",
    status: str = "OPEN",
    release_effect: str = "BLOCKS_RELEASE",
    closure: Any = None,
) -> dict[str, Any]:
    return {
        "condition_id": condition_id,
        "description": description,
        "owner": owner,
        "priority": priority,
        "status": status,
        "release_effect": release_effect,
        "closure_evidence_reference": closure,
    }


def _register(
    *,
    disposition_id: str = VALID_DISPOSITION_ID,
    scope_id: str = VALID_SCOPE_ID,
    scope_sha: str = VALID_SCOPE_SHA,
    conditions: Any = None,
) -> dict[str, Any]:
    register = {
        "schema_version": "1",
        "register_id": VALID_REGISTER_ID,
        "disposition_id": disposition_id,
        "scope_id": scope_id,
        "scope_sha256": scope_sha,
        "conditions": [] if conditions is None else conditions,
        "release_authorization_performed": False,
        "authority_profile": "UNRESOLVED_CONDITION_TRACKING",
        "boundary": gd.CONDITION_REGISTER_BOUNDARY,
    }
    register["register_sha256"] = gd._condition_register_hash(register)
    return register


def _record(
    *,
    disposition_id: str = VALID_DISPOSITION_ID,
    scope_id: str = VALID_SCOPE_ID,
    scope_sha: str = VALID_SCOPE_SHA,
    refs: Any = None,
    register: Any = None,
    state: str = "DEFER",
) -> dict[str, Any]:
    if refs is None:
        refs = [
            {
                "opinion_id": VALID_OPINION_ID,
                "opinion_sha256": VALID_OPINION_SHA,
                "review_track": "SECURITY",
                "opinion_state": "OBJECT",
                "reviewer_key": "reviewer-a",
            }
        ]
    if register is None:
        register = _register(disposition_id=disposition_id, scope_id=scope_id, scope_sha=scope_sha)
    record = {
        "schema_version": "1",
        "disposition_id": disposition_id,
        "scope_id": scope_id,
        "scope_sha256": scope_sha,
        "addressed_opinions": refs,
        "disposition_state": state,
        "owner_claim": _owner(),
        "recorded_at": "2026-08-07T00:00:00Z",
        "recorded_by": "local-user",
        "rationale": "Synthetic disposition.",
        "condition_register": register,
        "release_authorization_performed": False,
        "authority_profile": "CLAIMED_OWNER_ATTRIBUTION",
        "boundary": gd.OWNER_DISPOSITION_BOUNDARY,
    }
    record["disposition_sha256"] = gd._disposition_hash(record)
    return record


@pytest.mark.parametrize("value", [None, 7, "A" * 64, "f" * 63, "g" * 64])
def test_validate_sha256_rejects_invalid_values(value: Any) -> None:
    with pytest.raises(ValueError, match="64-character lowercase hexadecimal"):
        gd._validate_sha256(value, "digest")


def test_validate_sha256_accepts_digest() -> None:
    assert gd._validate_sha256("f" * 64, "digest") == "f" * 64


@pytest.mark.parametrize(
    ("boundary", "locator", "message"),
    [
        ("UNKNOWN", "a.json", "Unsupported evidence storage boundary"),
        ("PUBLIC_GIT", "", "must not be empty"),
        ("PROTECTED_WORKSPACE", "secret/file.json", "requires an opaque protected-ref"),
        ("PROTECTED_WORKSPACE", "protected-ref:bad ref", "protected evidence reference"),
        ("PUBLIC_GIT", "protected-ref:receipt", "reserved for PROTECTED_WORKSPACE"),
        ("PUBLIC_GIT", "folder\\file.json", "POSIX separators"),
        ("PUBLIC_GIT", "/absolute.json", "normalized relative POSIX path"),
        ("PUBLIC_GIT", "a/../b.json", "normalized relative POSIX path"),
    ],
)
def test_locator_validation_fail_closed(boundary: str, locator: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        gd._validate_locator(boundary, locator)


def test_locator_validation_accepts_public_and_protected() -> None:
    gd._validate_locator("PUBLIC_GIT", "evidence/receipt.json")
    gd._validate_locator("PROTECTED_WORKSPACE", "protected-ref:receipt-1")


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("not-an-object", "must be an object"),
        ({"label": "", "sha256": "a" * 64, "storage_boundary": "PUBLIC_GIT", "locator": "x"}, "label is required"),
        ({"label": "x", "sha256": "bad", "storage_boundary": "PUBLIC_GIT", "locator": "x"}, "64-character"),
    ],
)
def test_evidence_reference_validation_errors(value: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        gd._normalize_evidence_reference(value, "closure")


def test_load_dispositions_ignores_non_object_json(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    root = workspace.root / "governance" / "owner-dispositions"
    root.mkdir(parents=True, exist_ok=True)
    atomic_write_json(root / "ignored.json", ["not", "a", "record"])
    assert gd.load_governance_owner_dispositions(workspace) == []


def test_duplicate_indexes_are_refused() -> None:
    with pytest.raises(ValueError, match="Duplicate governance owner disposition ID"):
        gd._disposition_index([{"disposition_id": "x"}, {"disposition_id": "x"}])
    with pytest.raises(ValueError, match="Duplicate governance opinion ID"):
        gd._opinion_index([{"opinion_id": "x"}, {"opinion_id": "x"}])


@pytest.mark.parametrize(
    ("claim", "message"),
    [
        ("owner", "must be an object"),
        (
            {"owner_key": "bad owner", "name_or_role": "Owner", "accountability_state": "CLAIMED"},
            "owner_claim.owner_key",
        ),
        ({"owner_key": "owner", "name_or_role": "", "accountability_state": "CLAIMED"}, "name_or_role is required"),
        (
            {"owner_key": "owner", "name_or_role": "Owner", "accountability_state": ""},
            "accountability_state is required",
        ),
    ],
)
def test_owner_claim_validation(claim: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        gd._normalize_owner_claim(claim)


def test_owner_claim_optional_organization() -> None:
    assert gd._normalize_owner_claim(
        {"owner_key": "owner", "name_or_role": "Owner", "accountability_state": "CLAIMED"}
    ) == {"owner_key": "owner", "name_or_role": "Owner", "accountability_state": "CLAIMED"}


@pytest.mark.parametrize(
    ("condition", "message"),
    [
        ("bad", "must be an object"),
        (_condition(condition_id="wrong-prefix"), "GOVCOND- prefix"),
        (_condition(description=""), "description is required"),
        (_condition(owner="bad owner"), "conditions.0.owner"),
        (_condition(priority="URGENT"), "Unsupported condition priority"),
        (_condition(status="DONE"), "Unsupported condition status"),
        (_condition(release_effect="MAYBE"), "Unsupported condition release effect"),
        (_condition(status="RESOLVED"), "require closure_evidence_reference"),
        (
            _condition(
                status="OPEN",
                closure={"label": "x", "sha256": "a" * 64, "storage_boundary": "PUBLIC_GIT", "locator": "x"},
            ),
            "Only RESOLVED",
        ),
    ],
)
def test_condition_normalization_rejects_invalid_inputs(condition: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        gd._normalize_conditions([condition], predecessor=None)  # type: ignore[list-item]


def test_condition_normalization_rejects_duplicate_ids() -> None:
    condition = _condition()
    with pytest.raises(ValueError, match="Duplicate condition_id"):
        gd._normalize_conditions([condition, dict(condition)], predecessor=None)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("description", "Changed description"),
        ("owner", "other-owner"),
        ("priority", "LOW"),
        ("release_effect", "NON_BLOCKING"),
    ],
)
def test_condition_core_fields_are_immutable(field: str, value: str) -> None:
    prior = _condition()
    predecessor = {"condition_register": {"conditions": [prior]}}
    successor = dict(prior)
    successor[field] = value
    with pytest.raises(ValueError, match=f"changes immutable field {field}"):
        gd._normalize_conditions([successor], predecessor=predecessor)


def test_predecessor_with_non_list_conditions_is_ignored() -> None:
    assert gd._normalize_conditions([], predecessor={"condition_register": {"conditions": "bad"}}) == []


def test_addressed_opinion_refs_edge_cases() -> None:
    opinion = _opinion()
    with pytest.raises(ValueError, match="At least one"):
        gd._addressed_opinion_refs([opinion], scope_id=VALID_SCOPE_ID, scope_sha256=VALID_SCOPE_SHA, opinion_ids=[])
    with pytest.raises(ValueError, match="Invalid opinion_id"):
        gd._addressed_opinion_refs(
            [opinion], scope_id=VALID_SCOPE_ID, scope_sha256=VALID_SCOPE_SHA, opinion_ids=["bad id"]
        )
    with pytest.raises(ValueError, match="outside the declared governance scope"):
        gd._addressed_opinion_refs(
            [opinion], scope_id="GOVSCOPE-" + "9" * 32, scope_sha256=VALID_SCOPE_SHA, opinion_ids=[VALID_OPINION_ID]
        )
    no_reviewer = gd._addressed_opinion_refs(
        [_opinion(reviewer="bad")],
        scope_id=VALID_SCOPE_ID,
        scope_sha256=VALID_SCOPE_SHA,
        opinion_ids=[VALID_OPINION_ID],
    )
    assert no_reviewer[0]["reviewer_key"] == ""


def _patch_record_dependencies(monkeypatch: pytest.MonkeyPatch, records: list[dict[str, Any]] | None = None) -> None:
    monkeypatch.setattr(gd, "verify_governance_reviewer_opinions", lambda workspace: {"valid": True, "errors": []})
    monkeypatch.setattr(gd, "load_governance_reviewer_opinions", lambda workspace: [_opinion()])
    monkeypatch.setattr(gd, "load_governance_owner_dispositions", lambda workspace: list(records or []))
    monkeypatch.setattr(gd, "verify_governance_owner_dispositions", lambda workspace: {"valid": True, "errors": []})


def _record_call(workspace: Workspace, **overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "workspace": workspace,
        "scope_id": VALID_SCOPE_ID,
        "scope_sha256": VALID_SCOPE_SHA,
        "opinion_ids": [VALID_OPINION_ID],
        "disposition_state": "DEFER",
        "owner_claim": _owner(),
        "rationale": "Synthetic rationale.",
    }
    values.update(overrides)
    return gd.record_governance_owner_disposition(**values)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"recorded_by": "bad actor"}, "recorded_by"),
        ({"actor": "bad actor"}, "actor"),
        ({"scope_id": "bad scope"}, "scope_id"),
        ({"scope_sha256": "bad"}, "scope_sha256"),
    ],
)
def test_record_identity_and_scope_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, overrides: dict[str, Any], message: str
) -> None:
    workspace = _workspace(tmp_path)
    _patch_record_dependencies(monkeypatch)
    with pytest.raises(ValueError, match=message):
        _record_call(workspace, **overrides)


def test_record_missing_and_inactive_predecessors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    _patch_record_dependencies(monkeypatch)
    with pytest.raises(ValueError, match="does not exist"):
        _record_call(workspace, supersedes_disposition_id=VALID_DISPOSITION_ID)

    predecessor = _record()
    successor = dict(predecessor)
    successor["disposition_id"] = "GOVDISP-" + "6" * 32
    successor["supersedes_disposition_id"] = predecessor["disposition_id"]
    successor["supersedes_disposition_sha256"] = predecessor["disposition_sha256"]
    _patch_record_dependencies(monkeypatch, [predecessor, successor])
    with pytest.raises(ValueError, match="current active disposition"):
        _record_call(workspace, supersedes_disposition_id=VALID_DISPOSITION_ID)


def test_record_rejects_corrupt_existing_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    predecessor = _record()
    monkeypatch.setattr(gd, "verify_governance_reviewer_opinions", lambda workspace: {"valid": True, "errors": []})
    monkeypatch.setattr(gd, "load_governance_reviewer_opinions", lambda workspace: [_opinion()])
    monkeypatch.setattr(gd, "load_governance_owner_dispositions", lambda workspace: [predecessor])
    monkeypatch.setattr(
        gd,
        "verify_governance_owner_dispositions",
        lambda workspace: {"valid": False, "errors": ["corrupt"]},
    )
    with pytest.raises(ValueError, match="Existing governance owner disposition store failed verification"):
        _record_call(workspace)


def test_record_rejects_malformed_predecessor_register(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    predecessor = _record()
    predecessor["condition_register"] = None
    _patch_record_dependencies(monkeypatch, [predecessor])
    with pytest.raises(ValueError, match="missing its condition register"):
        _record_call(workspace, supersedes_disposition_id=VALID_DISPOSITION_ID)


def test_record_schema_failure_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    _patch_record_dependencies(monkeypatch)
    monkeypatch.setattr(gd, "_schema_errors", lambda value: [{"message": "bad schema"}])
    with pytest.raises(ValueError, match="failed validation"):
        _record_call(workspace)


def test_record_output_collision_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    _patch_record_dependencies(monkeypatch)
    fixed = "7" * 32
    monkeypatch.setattr(gd, "uuid4", lambda: SimpleNamespace(hex=fixed))
    root = workspace.root / "governance" / "owner-dispositions"
    root.mkdir(parents=True, exist_ok=True)
    atomic_write_json(root / f"GOVDISP-{fixed}.json", {})
    with pytest.raises(ValueError, match="already exists"):
        _record_call(workspace)


def test_supersession_error_matrix() -> None:
    predecessor = _record()

    incomplete = _record(disposition_id="GOVDISP-" + "6" * 32)
    incomplete["supersedes_disposition_id"] = predecessor["disposition_id"]

    missing = _record(disposition_id="GOVDISP-" + "7" * 32)
    missing["supersedes_disposition_id"] = "GOVDISP-" + "8" * 32
    missing["supersedes_disposition_sha256"] = "e" * 64

    successor = _record(disposition_id="GOVDISP-" + "9" * 32)
    successor["supersedes_disposition_id"] = predecessor["disposition_id"]
    successor["supersedes_disposition_sha256"] = "wrong"
    successor["scope_sha256"] = "f" * 64
    successor["addressed_opinions"] = []
    successor_register = dict(successor["condition_register"])
    successor_register["supersedes_register_id"] = "wrong"
    successor_register["supersedes_register_sha256"] = "wrong"
    successor["condition_register"] = successor_register

    errors = gd._supersession_errors([predecessor, incomplete, missing, successor])
    assert any("incomplete supersession reference" in error for error in errors)
    assert any("is missing" in error for error in errors)
    assert any("superseded disposition hash mismatch" in error for error in errors)
    assert any("supersession changes scope_sha256" in error for error in errors)
    assert any("changes addressed opinion set" in error for error in errors)
    assert any("condition register predecessor ID mismatch" in error for error in errors)
    assert any("condition register predecessor hash mismatch" in error for error in errors)


def test_supersession_errors_detect_self_removed_conditions_and_field_drift() -> None:
    prior_condition = _condition()
    predecessor = _record(register=_register(conditions=[prior_condition]))

    self_ref = dict(predecessor)
    self_ref["supersedes_disposition_id"] = predecessor["disposition_id"]
    self_ref["supersedes_disposition_sha256"] = predecessor["disposition_sha256"]
    self_register = dict(predecessor["condition_register"])
    self_register["supersedes_register_id"] = self_register["register_id"]
    self_register["supersedes_register_sha256"] = self_register["register_sha256"]
    self_register["conditions"] = []
    self_ref["condition_register"] = self_register

    errors = gd._supersession_errors([self_ref])
    assert any("cannot supersede itself" in error for error in errors)

    removed_successor = _record(
        disposition_id="GOVDISP-" + "a" * 32,
        register=_register(disposition_id="GOVDISP-" + "a" * 32, conditions=[]),
    )
    removed_successor["supersedes_disposition_id"] = predecessor["disposition_id"]
    removed_successor["supersedes_disposition_sha256"] = predecessor["disposition_sha256"]
    removed_register = removed_successor["condition_register"]
    removed_register["supersedes_register_id"] = predecessor["condition_register"]["register_id"]
    removed_register["supersedes_register_sha256"] = predecessor["condition_register"]["register_sha256"]
    errors = gd._supersession_errors([predecessor, removed_successor])
    assert any("condition IDs removed" in error for error in errors)

    successor = _record(disposition_id="GOVDISP-" + "6" * 32, register=_register(disposition_id="GOVDISP-" + "6" * 32))
    successor["supersedes_disposition_id"] = predecessor["disposition_id"]
    successor["supersedes_disposition_sha256"] = predecessor["disposition_sha256"]
    changed = _condition(description="changed", owner="other-owner", priority="LOW", release_effect="NON_BLOCKING")
    register = _register(disposition_id=successor["disposition_id"], conditions=[changed])
    register["supersedes_register_id"] = predecessor["condition_register"]["register_id"]
    register["supersedes_register_sha256"] = predecessor["condition_register"]["register_sha256"]
    successor["condition_register"] = register
    errors = gd._supersession_errors([predecessor, successor])
    for field in ("description", "owner", "priority", "release_effect"):
        assert any(f"changes immutable field {field}" in error for error in errors)


def test_condition_error_matrix() -> None:
    assert "condition register missing" in gd._condition_errors({"disposition_id": VALID_DISPOSITION_ID})[0]

    bad_register = _register()
    bad_register["register_sha256"] = "bad"
    bad_register["disposition_id"] = "wrong"
    bad_register["scope_id"] = "wrong"
    bad_register["scope_sha256"] = "wrong"
    bad_register["boundary"] = "wrong"
    bad_register["release_authorization_performed"] = True
    bad_register["conditions"] = "not-a-list"
    errors = gd._condition_errors(_record(register=bad_register))
    assert any("register hash mismatch" in error for error in errors)
    assert any("register disposition_id mismatch" in error for error in errors)
    assert any("register scope_id mismatch" in error for error in errors)
    assert any("register scope_sha256 mismatch" in error for error in errors)
    assert any("boundary mismatch" in error for error in errors)
    assert any("must remain non-authorizing" in error for error in errors)
    assert any("conditions must be a list" in error for error in errors)


def test_condition_errors_cover_bad_entries_and_closure() -> None:
    duplicate = _condition()
    resolved_without = _condition(condition_id="GOVCOND-" + "6" * 32, status="RESOLVED")
    unresolved_with_bad = _condition(
        condition_id="bad-id",
        priority="URGENT",
        status="UNKNOWN",
        release_effect="MAYBE",
        closure={"label": "", "sha256": "bad", "storage_boundary": "UNKNOWN", "locator": ""},
    )
    register = _register(conditions=["bad", duplicate, dict(duplicate), resolved_without, unresolved_with_bad])
    register["register_sha256"] = gd._condition_register_hash(register)
    errors = gd._condition_errors(_record(register=register))
    assert any("condition 0 is not an object" in error for error in errors)
    assert any("duplicate condition ID" in error for error in errors)
    assert any("invalid condition ID" in error for error in errors)
    assert any("invalid priority" in error for error in errors)
    assert any("invalid status" in error for error in errors)
    assert any("invalid release effect" in error for error in errors)
    assert any("lacks closure evidence" in error for error in errors)
    assert any("has closure evidence" in error for error in errors)
    assert any("invalid closure evidence" in error for error in errors)


def test_verify_covers_corruption_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    opinion = _opinion()
    bad_ref = {
        "opinion_id": VALID_OPINION_ID,
        "opinion_sha256": "wrong",
        "review_track": "METHODOLOGY",
        "opinion_state": "SUPPORT",
        "reviewer_key": "wrong-reviewer",
    }
    missing_ref = {
        "opinion_id": "GOVOP-" + "9" * 32,
        "opinion_sha256": "9" * 64,
        "review_track": "SECURITY",
        "opinion_state": "OBJECT",
        "reviewer_key": "reviewer-z",
    }
    record = _record(refs=["bad-ref", bad_ref, dict(bad_ref), missing_ref], state="ACCEPT_WITH_ACTION")
    record["_unexpected"] = True
    record["boundary"] = "wrong"
    record["disposition_state"] = "UNKNOWN"
    record["release_authorization_performed"] = True
    record["disposition_sha256"] = "wrong"
    record["condition_register"] = _register(conditions=[])

    monkeypatch.setattr(gd, "load_governance_owner_dispositions", lambda workspace: [record, dict(record)])
    monkeypatch.setattr(
        gd, "verify_governance_reviewer_opinions", lambda workspace: {"valid": False, "errors": ["bad"]}
    )
    monkeypatch.setattr(gd, "load_governance_reviewer_opinions", lambda workspace: [opinion])
    monkeypatch.setattr(gd, "load_events", lambda path: [])
    monkeypatch.setattr(gd, "_schema_errors", lambda value: [{"message": "schema"}])
    monkeypatch.setattr(gd, "_condition_errors", lambda value: [])
    monkeypatch.setattr(
        gd,
        "verify_chain",
        lambda path: {
            "valid": False,
            "errors": ["chain-bad"],
            "trailer_valid": False,
            "trailer_errors": ["trailer-bad"],
        },
    )

    result = gd.verify_governance_owner_dispositions(workspace)
    assert result["valid"] is False
    joined = "\n".join(result["errors"])
    for expected in (
        "governance reviewer opinion store is invalid",
        "duplicate disposition_id",
        "unsupported private fields",
        "hash mismatch",
        "schema invalid",
        "authority boundary mismatch",
        "unsupported disposition state",
        "release authorization must remain false",
        "addressed opinion reference is not an object",
        "duplicate addressed opinion",
        "opinion GOVOP-" + "9" * 32 + " is missing",
        "opinion " + VALID_OPINION_ID + " hash mismatch",
        "review_track mismatch",
        "opinion_state mismatch",
        "reviewer_key mismatch",
        "matching append-only event is missing",
        "event chain: chain-bad",
        "event chain trailer: trailer-bad",
    ):
        assert expected in joined


def test_verify_detects_scope_mismatches_and_accept_with_action_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    opinion = _opinion(scope_id="GOVSCOPE-" + "8" * 32, scope_sha="8" * 64)
    record = _record(state="ACCEPT_WITH_ACTION", register=_register(conditions=[]))
    monkeypatch.setattr(gd, "load_governance_owner_dispositions", lambda workspace: [record])
    monkeypatch.setattr(gd, "verify_governance_reviewer_opinions", lambda workspace: {"valid": True, "errors": []})
    monkeypatch.setattr(gd, "load_governance_reviewer_opinions", lambda workspace: [opinion])
    monkeypatch.setattr(gd, "load_events", lambda path: [])
    monkeypatch.setattr(gd, "_schema_errors", lambda value: [])
    monkeypatch.setattr(
        gd, "verify_chain", lambda path: {"valid": True, "errors": [], "trailer_valid": True, "trailer_errors": []}
    )
    result = gd.verify_governance_owner_dispositions(workspace)
    joined = "\n".join(result["errors"])
    assert "ACCEPT_WITH_ACTION requires conditions" in joined
    assert "scope ID mismatch" in joined
    assert "scope hash mismatch" in joined


def test_verify_handles_duplicate_opinion_index_and_event_load_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    opinion = _opinion()
    monkeypatch.setattr(gd, "load_governance_owner_dispositions", lambda workspace: [])
    monkeypatch.setattr(gd, "verify_governance_reviewer_opinions", lambda workspace: {"valid": True, "errors": []})
    monkeypatch.setattr(gd, "load_governance_reviewer_opinions", lambda workspace: [opinion, dict(opinion)])
    monkeypatch.setattr(gd, "load_events", lambda path: (_ for _ in ()).throw(ValueError("bad events")))
    monkeypatch.setattr(
        gd, "verify_chain", lambda path: {"valid": True, "errors": [], "trailer_valid": True, "trailer_errors": []}
    )
    result = gd.verify_governance_owner_dispositions(workspace)
    assert result["valid"] is False
    assert any("Duplicate governance opinion ID" in error for error in result["errors"])
    assert any("event log load failed" in error for error in result["errors"])


def test_verify_warns_about_unaddressed_active_opinion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    monkeypatch.setattr(gd, "load_governance_owner_dispositions", lambda workspace: [])
    monkeypatch.setattr(gd, "verify_governance_reviewer_opinions", lambda workspace: {"valid": True, "errors": []})
    monkeypatch.setattr(gd, "load_governance_reviewer_opinions", lambda workspace: [_opinion()])
    monkeypatch.setattr(gd, "load_events", lambda path: [])
    monkeypatch.setattr(
        gd, "verify_chain", lambda path: {"valid": True, "errors": [], "trailer_valid": True, "trailer_errors": []}
    )
    result = gd.verify_governance_owner_dispositions(workspace)
    assert result["valid"] is True
    assert result["counts"]["unaddressed_active_opinions"] == 1
    assert result["warnings"]


def test_summary_skips_malformed_and_resolved_conditions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    record = _record(
        register=_register(
            conditions=[
                "bad",
                _condition(condition_id="GOVCOND-" + "6" * 32, status="RESOLVED", closure={"x": "y"}),
                _condition(condition_id="GOVCOND-" + "7" * 32, release_effect="NON_BLOCKING"),
            ]
        )
    )
    malformed = _record(disposition_id="GOVDISP-" + "8" * 32, register="bad")
    monkeypatch.setattr(gd, "verify_governance_owner_dispositions", lambda workspace: {"valid": False})
    monkeypatch.setattr(gd, "load_governance_owner_dispositions", lambda workspace: [record, malformed])
    monkeypatch.setattr(gd, "load_governance_reviewer_opinions", lambda workspace: [_opinion()])
    summary = gd.summarize_governance_owner_dispositions(workspace)
    assert summary["integrity_valid"] is False
    assert len(summary["unresolved_conditions"]) == 1
    assert summary["unresolved_conditions"][0]["release_effect"] == "NON_BLOCKING"
    assert summary["release_blocking_condition_present"] is False
    assert summary["release_blocking_conditions"] == []


def test_summary_handles_non_object_reviewer_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    monkeypatch.setattr(gd, "verify_governance_owner_dispositions", lambda workspace: {"valid": True})
    monkeypatch.setattr(gd, "load_governance_owner_dispositions", lambda workspace: [])
    monkeypatch.setattr(gd, "load_governance_reviewer_opinions", lambda workspace: [_opinion(reviewer="bad")])
    summary = gd.summarize_governance_owner_dispositions(workspace)
    assert summary["unaddressed_active_opinions"][0]["reviewer_key"] is None
