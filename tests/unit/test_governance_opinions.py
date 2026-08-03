from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.events import append_event, load_events
from neuroai_workbench.governance_opinions import (
    GOVERNANCE_OPINION_BOUNDARY,
    _hash_record,
    _scope_manifest_sha256,
    _scope_records_by_id,
    _supersession_errors,
    load_governance_reviewer_opinions,
    record_governance_reviewer_opinion,
    summarize_governance_reviewer_opinions,
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
        scope_label="Reviewer opinion fixture",
        objects=objects,
        boundary_roots={"PUBLIC_GIT": public, "GENERATED_OUTPUT": generated, "ARCHIVE": archive},
    )
    return workspace, result["manifest"]


def _claim(reviewer_key: str, *, organization: str | None = None) -> dict[str, str]:
    claim = {
        "reviewer_key": reviewer_key,
        "name_or_role": f"Reviewer {reviewer_key}",
        "accountability_state": "CLAIMED_LOCAL_IDENTITY",
        "independence_statement": "No operational role in the reviewed implementation is claimed.",
        "conflict_of_interest_disclosure": "No conflict declared for this synthetic fixture.",
    }
    if organization:
        claim["organization"] = organization
    return claim


def _record(
    workspace: Workspace,
    scope: dict[str, object],
    *,
    reviewer_key: str = "reviewer-a",
    track: str = "SECURITY",
    state: str = "SUPPORT",
    supersedes: str | None = None,
    conditions: list[str] | None = None,
    evidence_requests: list[str] | None = None,
    evidence_references: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return record_governance_reviewer_opinion(
        workspace,
        scope_id=str(scope["scope_id"]),
        scope_sha256=str(scope["manifest_sha256"]),
        review_track=track,
        opinion_state=state,
        reviewer_claim=_claim(reviewer_key, organization="Example organization"),
        rationale=f"Synthetic {state} rationale.",
        conditions=conditions,
        evidence_requests=evidence_requests,
        evidence_references=evidence_references,
        supersedes_opinion_id=supersedes,
    )


def test_record_verify_and_summarize_support(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    result = _record(
        workspace,
        scope,
        evidence_references=[
            {
                "label": "Public method note",
                "sha256": "a" * 64,
                "storage_boundary": "PUBLIC_GIT",
                "locator": "docs/method-note.json",
            },
            {
                "label": "Protected evidence",
                "sha256": "b" * 64,
                "storage_boundary": "PROTECTED_WORKSPACE",
                "locator": "protected-ref:review-evidence-1",
            },
        ],
    )
    opinion = result["opinion"]
    assert opinion["opinion_sha256"] == _hash_record(opinion)
    assert opinion["boundary"] == GOVERNANCE_OPINION_BOUNDARY
    assert opinion["release_authorization_performed"] is False
    assert {item["storage_boundary"] for item in opinion["evidence_references"]} == {
        "PUBLIC_GIT",
        "PROTECTED_WORKSPACE",
    }

    verification = verify_governance_reviewer_opinions(workspace)
    assert verification["valid"] is True
    assert verification["counts"]["opinions"] == 1
    assert verification["counts"]["active_opinions"] == 1
    assert verification["event_chain_valid"] is True

    summary = summarize_governance_reviewer_opinions(workspace)
    assert summary["integrity_valid"] is True
    assert summary["active_state_counts"] == {"SUPPORT": 1}
    assert summary["disagreement_present"] is False
    assert summary["release_readiness_established"] is False
    assert summary["by_track"]["SECURITY"][0]["reviewer_key"] == "reviewer-a"

    events = load_events(workspace.root / "events.jsonl")
    assert events[-1]["action"] == "GOVERNANCE_REVIEWER_OPINION_RECORDED"
    assert events[-1]["payload"]["opinion_id"] == opinion["opinion_id"]


def test_disagreement_abstention_and_evidence_request_remain_visible(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    _record(workspace, scope, reviewer_key="supporter", state="SUPPORT")
    _record(workspace, scope, reviewer_key="objector", state="OBJECT")
    _record(workspace, scope, reviewer_key="abstainer", track="METHODOLOGY", state="ABSTAIN")
    _record(
        workspace,
        scope,
        reviewer_key="requester",
        track="DATA_GOVERNANCE",
        state="REQUEST_EVIDENCE",
        evidence_requests=["Provide the protected source-retention receipt."],
    )
    _record(
        workspace,
        scope,
        reviewer_key="conditional",
        track="ACCESSIBILITY",
        state="SUPPORT_WITH_CONDITIONS",
        conditions=["Publish an accessible HTML rendering."],
    )

    summary = summarize_governance_reviewer_opinions(workspace)
    assert summary["disagreement_present"] is True
    assert summary["disagreement_tracks"] == ["SECURITY"]
    assert summary["objection_present"] is True
    assert summary["abstention_present"] is True
    assert summary["evidence_request_present"] is True
    assert summary["conditions_present"] is True
    assert summary["active_state_counts"] == {
        "ABSTAIN": 1,
        "OBJECT": 1,
        "REQUEST_EVIDENCE": 1,
        "SUPPORT": 1,
        "SUPPORT_WITH_CONDITIONS": 1,
    }


def test_supersession_preserves_history_and_changes_only_active_view(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    first = _record(workspace, scope, state="SUPPORT")["opinion"]
    second = _record(
        workspace,
        scope,
        state="OBJECT",
        supersedes=str(first["opinion_id"]),
    )["opinion"]

    records = load_governance_reviewer_opinions(workspace)
    assert len(records) == 2
    assert second["supersedes_opinion_id"] == first["opinion_id"]
    assert second["supersedes_opinion_sha256"] == first["opinion_sha256"]

    verification = verify_governance_reviewer_opinions(workspace)
    assert verification["valid"] is True
    assert verification["counts"]["active_opinions"] == 1
    assert verification["counts"]["superseded_opinions"] == 1
    summary = summarize_governance_reviewer_opinions(workspace)
    assert summary["active_state_counts"] == {"OBJECT": 1}
    assert summary["by_track"]["SECURITY"][0]["opinion_id"] == second["opinion_id"]


def test_duplicate_active_opinion_requires_explicit_supersession(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    first = _record(workspace, scope)["opinion"]
    with pytest.raises(ValueError, match="explicit supersession is required"):
        _record(workspace, scope, state="OBJECT")
    with pytest.raises(ValueError, match="does not exist"):
        _record(workspace, scope, state="OBJECT", supersedes="GOVOP-" + "0" * 32)
    with pytest.raises(ValueError, match="current active opinion"):
        _record(
            workspace,
            scope,
            reviewer_key="reviewer-b",
            state="OBJECT",
            supersedes=str(first["opinion_id"]),
        )


def test_opinion_state_and_reviewer_claim_validation(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    common = {
        "workspace": workspace,
        "scope_id": str(scope["scope_id"]),
        "scope_sha256": str(scope["manifest_sha256"]),
        "review_track": "SECURITY",
        "opinion_state": "SUPPORT",
        "reviewer_claim": _claim("reviewer-a"),
        "rationale": "Rationale",
    }
    with pytest.raises(ValueError, match="Unsupported governance review track"):
        record_governance_reviewer_opinion(**{**common, "review_track": "UNKNOWN"})
    with pytest.raises(ValueError, match="Unsupported governance opinion state"):
        record_governance_reviewer_opinion(**{**common, "opinion_state": "UNKNOWN"})
    with pytest.raises(ValueError, match="rationale must not be empty"):
        record_governance_reviewer_opinion(**{**common, "rationale": " "})
    with pytest.raises(ValueError, match="reviewer_claim must be an object"):
        record_governance_reviewer_opinion(**{**common, "reviewer_claim": []})  # type: ignore[arg-type]
    for field in (
        "name_or_role",
        "accountability_state",
        "independence_statement",
        "conflict_of_interest_disclosure",
    ):
        claim = _claim("reviewer-a")
        claim[field] = ""
        with pytest.raises(ValueError, match=field):
            record_governance_reviewer_opinion(**{**common, "reviewer_claim": claim})
    with pytest.raises(ValueError, match="requires at least one condition"):
        record_governance_reviewer_opinion(**{**common, "opinion_state": "SUPPORT_WITH_CONDITIONS"})
    with pytest.raises(ValueError, match="requires at least one evidence request"):
        record_governance_reviewer_opinion(**{**common, "opinion_state": "REQUEST_EVIDENCE"})


def test_scope_binding_is_fail_closed(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    with pytest.raises(ValueError, match="does not exist"):
        record_governance_reviewer_opinion(
            workspace,
            scope_id="GOVSCOPE-" + "0" * 32,
            scope_sha256=str(scope["manifest_sha256"]),
            review_track="SECURITY",
            opinion_state="SUPPORT",
            reviewer_claim=_claim("reviewer-a"),
            rationale="Rationale",
        )
    with pytest.raises(ValueError, match="does not match"):
        record_governance_reviewer_opinion(
            workspace,
            scope_id=str(scope["scope_id"]),
            scope_sha256="0" * 64,
            review_track="SECURITY",
            opinion_state="SUPPORT",
            reviewer_claim=_claim("reviewer-a"),
            rationale="Rationale",
        )
    with pytest.raises(ValueError, match="64-character"):
        record_governance_reviewer_opinion(
            workspace,
            scope_id=str(scope["scope_id"]),
            scope_sha256="invalid",
            review_track="SECURITY",
            opinion_state="SUPPORT",
            reviewer_claim=_claim("reviewer-a"),
            rationale="Rationale",
        )


def test_evidence_reference_validation(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    invalid_references = [
        ["invalid"],
        [{"label": "", "sha256": "a" * 64, "storage_boundary": "PUBLIC_GIT", "locator": "x"}],
        [{"label": "x", "sha256": "invalid", "storage_boundary": "PUBLIC_GIT", "locator": "x"}],
        [{"label": "x", "sha256": "a" * 64, "storage_boundary": "UNKNOWN", "locator": "x"}],
        [{"label": "x", "sha256": "a" * 64, "storage_boundary": "PUBLIC_GIT", "locator": "../x"}],
        [{"label": "x", "sha256": "a" * 64, "storage_boundary": "PUBLIC_GIT", "locator": "protected-ref:x"}],
        [{"label": "x", "sha256": "a" * 64, "storage_boundary": "PROTECTED_WORKSPACE", "locator": "private/x"}],
    ]
    for references in invalid_references:
        with pytest.raises(ValueError):
            _record(workspace, scope, evidence_references=references)  # type: ignore[arg-type]

    duplicate = {
        "label": "x",
        "sha256": "a" * 64,
        "storage_boundary": "PUBLIC_GIT",
        "locator": "x.json",
    }
    with pytest.raises(ValueError, match="duplicates an earlier"):
        _record(workspace, scope, evidence_references=[duplicate, duplicate])


def test_tampering_missing_scope_and_missing_event_are_detected(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    result = _record(workspace, scope)
    path = Path(str(result["path"]))
    opinion = json.loads(path.read_text(encoding="utf-8"))
    opinion["rationale"] = "Tampered rationale"
    atomic_write_json(path, opinion)
    report = verify_governance_reviewer_opinions(workspace)
    assert report["valid"] is False
    assert any("hash mismatch" in error for error in report["errors"])

    opinion["opinion_sha256"] = _hash_record(opinion)
    opinion["scope_sha256"] = "0" * 64
    opinion["opinion_sha256"] = _hash_record(opinion)
    atomic_write_json(path, opinion)
    report = verify_governance_reviewer_opinions(workspace)
    assert any("governance scope hash mismatch" in error for error in report["errors"])

    opinion["scope_id"] = "GOVSCOPE-" + "0" * 32
    opinion["opinion_sha256"] = _hash_record(opinion)
    atomic_write_json(path, opinion)
    report = verify_governance_reviewer_opinions(workspace)
    assert any("governance scope" in error and "is missing" in error for error in report["errors"])
    assert any("matching append-only event is missing" in error for error in report["errors"])


def test_supersession_graph_rejects_branching_cycles_and_substitution() -> None:
    base = {
        "scope_id": "GOVSCOPE-" + "1" * 32,
        "scope_sha256": "a" * 64,
        "review_track": "SECURITY",
        "reviewer_claim": {"reviewer_key": "reviewer-a"},
    }
    first = {**base, "opinion_id": "GOVOP-" + "1" * 32, "opinion_sha256": "b" * 64}
    second = {
        **base,
        "opinion_id": "GOVOP-" + "2" * 32,
        "opinion_sha256": "c" * 64,
        "supersedes_opinion_id": first["opinion_id"],
        "supersedes_opinion_sha256": first["opinion_sha256"],
    }
    third = {
        **base,
        "opinion_id": "GOVOP-" + "3" * 32,
        "opinion_sha256": "d" * 64,
        "supersedes_opinion_id": first["opinion_id"],
        "supersedes_opinion_sha256": first["opinion_sha256"],
    }
    errors = _supersession_errors([first, second, third])
    assert any("branching supersession" in error for error in errors)

    cycle_a = {
        **base,
        "opinion_id": "GOVOP-" + "4" * 32,
        "opinion_sha256": "e" * 64,
        "supersedes_opinion_id": "GOVOP-" + "5" * 32,
        "supersedes_opinion_sha256": "f" * 64,
    }
    cycle_b = {
        **base,
        "opinion_id": "GOVOP-" + "5" * 32,
        "opinion_sha256": "f" * 64,
        "supersedes_opinion_id": cycle_a["opinion_id"],
        "supersedes_opinion_sha256": cycle_a["opinion_sha256"],
    }
    errors = _supersession_errors([cycle_a, cycle_b])
    assert any("cycle detected" in error for error in errors)

    changed_track = {**second, "review_track": "METHODOLOGY"}
    changed_reviewer = {**second, "reviewer_claim": {"reviewer_key": "reviewer-b"}}
    changed_hash = {**second, "supersedes_opinion_sha256": "0" * 64}
    incomplete = {**second}
    incomplete.pop("supersedes_opinion_sha256")
    missing = {**second, "supersedes_opinion_id": "GOVOP-" + "9" * 32}
    self_reference = {
        **second,
        "supersedes_opinion_id": second["opinion_id"],
        "supersedes_opinion_sha256": second["opinion_sha256"],
    }
    assert any("changes review_track" in error for error in _supersession_errors([first, changed_track]))
    assert any("changes reviewer_key" in error for error in _supersession_errors([first, changed_reviewer]))
    assert any("hash mismatch" in error for error in _supersession_errors([first, changed_hash]))
    assert any("incomplete supersession" in error for error in _supersession_errors([first, incomplete]))
    assert any("is missing" in error for error in _supersession_errors([first, missing]))
    assert any("cannot supersede itself" in error for error in _supersession_errors([first, self_reference]))


def test_duplicate_ids_non_object_files_and_corrupt_event_log(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    result = _record(workspace, scope)
    opinion = result["opinion"]
    root = workspace.root / "governance" / "opinions"
    atomic_write_json(root / "duplicate.json", opinion)
    atomic_write_json(root / "non-object.json", ["ignored"])
    assert len(load_governance_reviewer_opinions(workspace)) == 2
    report = verify_governance_reviewer_opinions(workspace)
    assert report["valid"] is False
    assert any("duplicate opinion_id" in error for error in report["errors"])

    (workspace.root / "events.jsonl").write_text("{invalid-json\n", encoding="utf-8")
    report = verify_governance_reviewer_opinions(workspace)
    assert report["valid"] is False
    assert any("event log load failed" in error for error in report["errors"])
    assert report["event_chain_valid"] is False


def test_uuid_collision_is_append_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class _FixedUUID:
        hex = "a" * 32

    monkeypatch.setattr("neuroai_workbench.governance_opinions.uuid4", lambda: _FixedUUID())
    workspace, scope = _scope(tmp_path)
    first = _record(workspace, scope)["opinion"]
    with pytest.raises(ValueError, match="already exists"):
        _record(
            workspace,
            scope,
            reviewer_key="reviewer-b",
            track="METHODOLOGY",
        )
    assert first["opinion_id"] == "GOVOP-" + "a" * 32


def test_scope_store_integrity_and_existing_opinion_store_fail_closed(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    scope_path = next((workspace.root / "governance" / "scopes").glob("*.json"))
    stored_scope = json.loads(scope_path.read_text(encoding="utf-8"))
    stored_scope["scope_label"] = "Tampered scope label"
    atomic_write_json(scope_path, stored_scope)
    with pytest.raises(ValueError, match="failed canonical hash verification"):
        _record(workspace, scope)
    report = verify_governance_reviewer_opinions(workspace)
    assert report["valid"] is False
    assert any("governance scope store invalid" in error for error in report["errors"])

    workspace, scope = _scope(tmp_path / "opinion-store")
    result = _record(workspace, scope)
    opinion_path = Path(str(result["path"]))
    opinion = json.loads(opinion_path.read_text(encoding="utf-8"))
    opinion["rationale"] = "Tampered existing opinion"
    atomic_write_json(opinion_path, opinion)
    with pytest.raises(ValueError, match="Existing governance opinion store failed verification"):
        _record(
            workspace,
            scope,
            reviewer_key="reviewer-b",
            track="METHODOLOGY",
        )


def test_exactly_one_matching_event_is_required(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    result = _record(workspace, scope)
    opinion = result["opinion"]
    append_event(
        workspace.root / "events.jsonl",
        "GOVERNANCE_REVIEWER_OPINION_RECORDED",
        "local-user",
        {
            "opinion_id": opinion["opinion_id"],
            "opinion_sha256": opinion["opinion_sha256"],
            "scope_id": opinion["scope_id"],
            "scope_sha256": opinion["scope_sha256"],
            "review_track": opinion["review_track"],
            "opinion_state": opinion["opinion_state"],
            "reviewer_key": opinion["reviewer_claim"]["reviewer_key"],
            "supersedes_opinion_id": None,
            "release_authorization_performed": False,
        },
    )
    report = verify_governance_reviewer_opinions(workspace)
    assert report["valid"] is False
    assert any("2 matching append-only events" in error for error in report["errors"])


def test_scope_store_defensive_branches(tmp_path: Path) -> None:
    workspace, _ = _scope(tmp_path / "missing-id")
    scope_path = next((workspace.root / "governance" / "scopes").glob("*.json"))
    stored = json.loads(scope_path.read_text(encoding="utf-8"))
    stored.pop("scope_id")
    atomic_write_json(scope_path, stored)
    with pytest.raises(ValueError, match="missing scope_id"):
        _scope_records_by_id(workspace)

    workspace, _ = _scope(tmp_path / "private-field")
    scope_path = next((workspace.root / "governance" / "scopes").glob("*.json"))
    stored = json.loads(scope_path.read_text(encoding="utf-8"))
    stored["_unbound"] = "authority"
    atomic_write_json(scope_path, stored)
    with pytest.raises(ValueError, match="unsupported private fields"):
        _scope_records_by_id(workspace)

    workspace, _ = _scope(tmp_path / "authorizing")
    scope_path = next((workspace.root / "governance" / "scopes").glob("*.json"))
    stored = json.loads(scope_path.read_text(encoding="utf-8"))
    stored["release_authorization_performed"] = True
    stored["manifest_sha256"] = _scope_manifest_sha256(stored)
    atomic_write_json(scope_path, stored)
    with pytest.raises(ValueError, match="must remain non-authorizing"):
        _scope_records_by_id(workspace)

    workspace, _ = _scope(tmp_path / "duplicate")
    scope_path = next((workspace.root / "governance" / "scopes").glob("*.json"))
    stored = json.loads(scope_path.read_text(encoding="utf-8"))
    atomic_write_json(scope_path.parent / "duplicate.json", stored)
    with pytest.raises(ValueError, match="Duplicate governance scope ID"):
        _scope_records_by_id(workspace)


def test_additional_evidence_locator_variants_fail_closed(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    locators = [
        ("PUBLIC_GIT", ""),
        ("PUBLIC_GIT", "nested\\object.json"),
        ("PUBLIC_GIT", "/absolute/object.json"),
        ("PUBLIC_GIT", "nested//object.json"),
        ("PROTECTED_WORKSPACE", "protected-ref:"),
    ]
    for index, (boundary, locator) in enumerate(locators):
        with pytest.raises(ValueError):
            _record(
                workspace,
                scope,
                reviewer_key=f"locator-{index}",
                track="METHODOLOGY",
                evidence_references=[
                    {
                        "label": "Invalid locator fixture",
                        "sha256": "a" * 64,
                        "storage_boundary": boundary,
                        "locator": locator,
                    }
                ],
            )


def test_persisted_semantic_tampering_is_reported(tmp_path: Path) -> None:
    def mutated_report(
        suffix: str,
        mutation: object,
    ) -> dict[str, object]:
        workspace, scope = _scope(tmp_path / suffix)
        result = _record(workspace, scope)
        path = Path(str(result["path"]))
        opinion = json.loads(path.read_text(encoding="utf-8"))
        assert callable(mutation)
        mutation(opinion)
        opinion["opinion_sha256"] = _hash_record(opinion)
        atomic_write_json(path, opinion)
        return verify_governance_reviewer_opinions(workspace)

    cases = [
        ("private", lambda item: item.__setitem__("_unbound", "authority"), "unsupported private fields"),
        ("boundary", lambda item: item.__setitem__("boundary", "authorizes release"), "authority boundary mismatch"),
        ("track", lambda item: item.__setitem__("review_track", "UNKNOWN"), "unsupported review track"),
        ("state", lambda item: item.__setitem__("opinion_state", "UNKNOWN"), "unsupported opinion state"),
        (
            "authorization",
            lambda item: item.__setitem__("release_authorization_performed", True),
            "release authorization must remain false",
        ),
        (
            "conditions",
            lambda item: item.__setitem__("opinion_state", "SUPPORT_WITH_CONDITIONS"),
            "conditions required",
        ),
        (
            "evidence-request",
            lambda item: item.__setitem__("opinion_state", "REQUEST_EVIDENCE"),
            "evidence requests required",
        ),
        (
            "evidence-reference",
            lambda item: item.__setitem__("evidence_references", ["invalid"]),
            "invalid evidence reference",
        ),
    ]
    for suffix, mutation, expected in cases:
        report = mutated_report(suffix, mutation)
        assert report["valid"] is False
        assert any(expected in error for error in report["errors"])


def test_duplicate_active_opinions_are_reported(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path)
    result = _record(workspace, scope)
    original = result["opinion"]
    duplicate = json.loads(json.dumps(original))
    duplicate["opinion_id"] = "GOVOP-" + "d" * 32
    duplicate["opinion_sha256"] = _hash_record(duplicate)
    root = workspace.root / "governance" / "opinions"
    atomic_write_json(root / f"{duplicate['opinion_id']}.json", duplicate)
    append_event(
        workspace.root / "events.jsonl",
        "GOVERNANCE_REVIEWER_OPINION_RECORDED",
        "local-user",
        {
            "opinion_id": duplicate["opinion_id"],
            "opinion_sha256": duplicate["opinion_sha256"],
            "scope_id": duplicate["scope_id"],
            "scope_sha256": duplicate["scope_sha256"],
            "review_track": duplicate["review_track"],
            "opinion_state": duplicate["opinion_state"],
            "reviewer_key": duplicate["reviewer_claim"]["reviewer_key"],
            "supersedes_opinion_id": None,
            "release_authorization_performed": False,
        },
    )
    report = verify_governance_reviewer_opinions(workspace)
    assert report["valid"] is False
    assert any("multiple active opinions" in error for error in report["errors"])


def test_additional_supersession_and_summary_fallbacks(tmp_path: Path) -> None:
    base = {
        "scope_id": "GOVSCOPE-" + "1" * 32,
        "scope_sha256": "a" * 64,
        "review_track": "SECURITY",
        "reviewer_claim": {"reviewer_key": "reviewer-a"},
    }
    first = {**base, "opinion_id": "GOVOP-" + "1" * 32, "opinion_sha256": "b" * 64}
    second = {
        **base,
        "opinion_id": "GOVOP-" + "2" * 32,
        "opinion_sha256": "c" * 64,
        "supersedes_opinion_id": first["opinion_id"],
        "supersedes_opinion_sha256": first["opinion_sha256"],
    }
    changed_scope_id = {**second, "scope_id": "GOVSCOPE-" + "2" * 32}
    changed_scope_hash = {**second, "scope_sha256": "d" * 64}
    changed_reviewer_type = {**second, "reviewer_claim": []}
    assert any("changes scope_id" in error for error in _supersession_errors([first, changed_scope_id]))
    assert any("changes scope_sha256" in error for error in _supersession_errors([first, changed_scope_hash]))
    assert any("changes reviewer_key" in error for error in _supersession_errors([first, changed_reviewer_type]))

    workspace, scope = _scope(tmp_path / "summary")
    result = _record(workspace, scope)
    path = Path(str(result["path"]))
    opinion = json.loads(path.read_text(encoding="utf-8"))
    opinion["review_track"] = "UNKNOWN"
    opinion["reviewer_claim"] = []
    opinion["opinion_sha256"] = _hash_record(opinion)
    atomic_write_json(path, opinion)
    summary = summarize_governance_reviewer_opinions(workspace)
    assert summary["integrity_valid"] is False
    assert summary["active_state_counts"] == {"SUPPORT": 1}
    assert all(not opinions for opinions in summary["by_track"].values())


def test_scope_event_and_authority_binding_fail_closed(tmp_path: Path) -> None:
    workspace, scope = _scope(tmp_path / "recomputed")
    scope_path = next((workspace.root / "governance" / "scopes").glob("*.json"))
    stored = json.loads(scope_path.read_text(encoding="utf-8"))
    stored["scope_label"] = "Recomputed tampered scope"
    stored["manifest_sha256"] = _scope_manifest_sha256(stored)
    atomic_write_json(scope_path, stored)
    with pytest.raises(ValueError, match="no matching append-only event"):
        _scope_records_by_id(workspace)
    with pytest.raises(ValueError, match="no matching append-only event"):
        _record(workspace, stored)

    workspace, scope = _scope(tmp_path / "duplicate-event")
    append_event(
        workspace.root / "events.jsonl",
        "GOVERNANCE_SCOPE_RECORDED",
        "local-user",
        {
            "scope_id": scope["scope_id"],
            "manifest_sha256": scope["manifest_sha256"],
            "object_count": len(scope["objects"]),
            "release_authorization_performed": False,
        },
    )
    with pytest.raises(ValueError, match="2 matching append-only events"):
        _scope_records_by_id(workspace)

    mutations = [
        ("schema", "schema_version", "2", "unsupported schema version"),
        ("profile", "authority_profile", "RELEASE_AUTHORITY", "invalid authority profile"),
        ("boundary", "boundary", "authorizes release", "invalid authority boundary"),
    ]
    for suffix, field, value, message in mutations:
        workspace, _ = _scope(tmp_path / suffix)
        path = next((workspace.root / "governance" / "scopes").glob("*.json"))
        record = json.loads(path.read_text(encoding="utf-8"))
        record[field] = value
        record["manifest_sha256"] = _scope_manifest_sha256(record)
        atomic_write_json(path, record)
        with pytest.raises(ValueError, match=message):
            _scope_records_by_id(workspace)
