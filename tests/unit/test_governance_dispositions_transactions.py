from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

import neuroai_workbench.governance_dispositions as gd
import neuroai_workbench.governance_transactions as tx
from neuroai_workbench.events import load_events
from neuroai_workbench.governance_opinions import record_governance_reviewer_opinion
from neuroai_workbench.governance_scope import record_governance_scope_manifest, scope_object_for_path
from neuroai_workbench.util import atomic_write_json
from neuroai_workbench.workspace import Workspace


def _fixture(tmp_path: Path) -> tuple[Workspace, dict[str, Any], dict[str, Any]]:
    workspace = Workspace.initialize(tmp_path / "workspace")
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
    scope = record_governance_scope_manifest(
        workspace,
        scope_label="Transaction integration fixture",
        objects=objects,
        boundary_roots={"PUBLIC_GIT": public, "GENERATED_OUTPUT": generated, "ARCHIVE": archive},
    )["manifest"]
    opinion = record_governance_reviewer_opinion(
        workspace,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        review_track="SECURITY",
        opinion_state="OBJECT",
        reviewer_claim={
            "reviewer_key": "synthetic-reviewer",
            "name_or_role": "Synthetic reviewer",
            "organization": "Synthetic fixture",
            "accountability_state": "CLAIMED_LOCAL_IDENTITY",
            "independence_statement": "Synthetic independence claim for software testing only.",
            "conflict_of_interest_disclosure": "Synthetic fixture; no real-human review claim.",
        },
        rationale="Synthetic objection used only to test persistence behavior.",
    )["opinion"]
    return workspace, scope, opinion


def _owner() -> dict[str, str]:
    return {
        "owner_key": "synthetic-owner",
        "name_or_role": "Synthetic local owner",
        "organization": "Synthetic fixture",
        "accountability_state": "CLAIMED_LOCAL_OWNER",
    }


def _record(
    workspace: Workspace,
    scope: dict[str, Any],
    opinion: dict[str, Any],
    *,
    state: str = "DEFER",
    supersedes: str | None = None,
    conditions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return gd.record_governance_owner_disposition(
        workspace,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        opinion_ids=[opinion["opinion_id"]],
        disposition_state=state,
        owner_claim=_owner(),
        rationale=f"Synthetic {state} disposition for transaction testing.",
        conditions=conditions,
        supersedes_disposition_id=supersedes,
    )["disposition"]


def _transaction_journals(workspace: Workspace) -> list[Path]:
    return sorted((workspace.root / "governance" / "transactions").glob("*.json"))


def test_disposition_event_binds_transaction_and_condition_register(tmp_path: Path) -> None:
    workspace, scope, opinion = _fixture(tmp_path)
    disposition = _record(workspace, scope, opinion)
    register = disposition["condition_register"]
    event = load_events(workspace.root / "events.jsonl")[-1]

    assert event["action"] == "GOVERNANCE_OWNER_DISPOSITION_RECORDED"
    assert event["payload"]["transaction_record_id"] == disposition["disposition_id"]
    assert event["payload"]["transaction_record_sha256"] == disposition["disposition_sha256"]
    assert event["payload"]["transaction_secondary_digests"] == {
        "condition_register_sha256": register["register_sha256"]
    }
    assert _transaction_journals(workspace) == []
    assert gd.verify_governance_owner_dispositions(workspace)["valid"] is True


def test_pre_event_disposition_crash_rolls_back_record_and_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, scope, opinion = _fixture(tmp_path)
    original = gd.append_governance_record_locked

    def crashing_append(*args: Any, **kwargs: Any) -> dict[str, Any]:
        def crash(phase: str) -> None:
            if phase == "AFTER_RECORD_WRITE":
                raise RuntimeError("synthetic pre-event crash")

        return original(*args, **kwargs, phase_hook=crash)

    monkeypatch.setattr(gd, "append_governance_record_locked", crashing_append)
    with pytest.raises(RuntimeError, match="synthetic pre-event crash"):
        _record(workspace, scope, opinion)

    assert list((workspace.root / "governance" / "owner-dispositions").glob("*.json")) == []
    assert _transaction_journals(workspace) == []
    assert not any(
        event["action"] == "GOVERNANCE_OWNER_DISPOSITION_RECORDED"
        for event in load_events(workspace.root / "events.jsonl")
    )


def test_post_event_disposition_error_remains_committed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, scope, opinion = _fixture(tmp_path)
    original = gd.append_governance_record_locked

    def crashing_append(*args: Any, **kwargs: Any) -> dict[str, Any]:
        def crash(phase: str) -> None:
            if phase == "AFTER_EVENT_APPEND":
                raise RuntimeError("synthetic caller failure after commit")

        return original(*args, **kwargs, phase_hook=crash)

    monkeypatch.setattr(gd, "append_governance_record_locked", crashing_append)
    with pytest.raises(RuntimeError, match="synthetic caller failure after commit"):
        _record(workspace, scope, opinion)

    records = gd.load_governance_owner_dispositions(workspace)
    assert len(records) == 1
    assert _transaction_journals(workspace) == []
    assert gd.verify_governance_owner_dispositions(workspace)["valid"] is True
    events = [
        event
        for event in load_events(workspace.root / "events.jsonl")
        if event["action"] == "GOVERNANCE_OWNER_DISPOSITION_RECORDED"
    ]
    assert len(events) == 1
    assert (
        events[0]["payload"]["transaction_secondary_digests"]["condition_register_sha256"]
        == records[0]["condition_register"]["register_sha256"]
    )


def test_concurrent_overlapping_dispositions_have_one_winner(tmp_path: Path) -> None:
    workspace, scope, opinion = _fixture(tmp_path)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    outcomes_lock = threading.Lock()

    def writer(label: str) -> None:
        barrier.wait()
        try:
            _record(workspace, scope, opinion, state="DEFER")
        except ValueError as exc:
            outcome = f"{label}:rejected:{exc}"
        else:
            outcome = f"{label}:committed"
        with outcomes_lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=writer, args=(label,)) for label in ("A", "B")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    assert sum(":committed" in outcome for outcome in outcomes) == 1
    assert sum(":rejected:" in outcome for outcome in outcomes) == 1
    assert any("already addresses opinion IDs" in outcome for outcome in outcomes if ":rejected:" in outcome)
    assert len(gd.load_governance_owner_dispositions(workspace)) == 1
    assert gd.verify_governance_owner_dispositions(workspace)["valid"] is True


def test_concurrent_supersessions_have_one_winner(tmp_path: Path) -> None:
    workspace, scope, opinion = _fixture(tmp_path)
    first = _record(workspace, scope, opinion, state="DEFER")
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    outcomes_lock = threading.Lock()

    def writer(label: str) -> None:
        barrier.wait()
        try:
            _record(
                workspace,
                scope,
                opinion,
                state="REJECT",
                supersedes=first["disposition_id"],
            )
        except ValueError as exc:
            outcome = f"{label}:rejected:{exc}"
        else:
            outcome = f"{label}:committed"
        with outcomes_lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=writer, args=(label,)) for label in ("A", "B")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    assert sum(":committed" in outcome for outcome in outcomes) == 1
    assert sum(":rejected:" in outcome for outcome in outcomes) == 1
    assert any("current active disposition" in outcome for outcome in outcomes if ":rejected:" in outcome)
    assert len(gd.load_governance_owner_dispositions(workspace)) == 2
    assert gd.verify_governance_owner_dispositions(workspace)["valid"] is True


def test_prepared_journal_does_not_copy_protected_closure_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, scope, opinion = _fixture(tmp_path)
    original_append = gd.append_governance_record_locked
    original_recovery = tx._recover_prepared_transactions_unlocked
    secret_label = "SENSITIVE-CLOSURE-LABEL-MUST-NOT-BE-COPIED-INTO-JOURNAL"

    class StopRecovery(BaseException):
        pass

    condition = {
        "description": "Synthetic resolved condition.",
        "owner": "synthetic-owner",
        "priority": "HIGH",
        "status": "RESOLVED",
        "release_effect": "NON_BLOCKING",
        "closure_evidence_reference": {
            "label": secret_label,
            "sha256": "c" * 64,
            "storage_boundary": "PROTECTED_WORKSPACE",
            "locator": "protected-ref:synthetic-closure",
        },
    }

    def interrupted_append(*args: Any, **kwargs: Any) -> dict[str, Any]:
        def crash(phase: str) -> None:
            if phase == "AFTER_JOURNAL_WRITE":
                monkeypatch.setattr(
                    tx,
                    "_recover_prepared_transactions_unlocked",
                    lambda _workspace: (_ for _ in ()).throw(StopRecovery()),
                )
                raise RuntimeError("synthetic process loss")

        return original_append(*args, **kwargs, phase_hook=crash)

    monkeypatch.setattr(gd, "append_governance_record_locked", interrupted_append)
    with pytest.raises(StopRecovery):
        _record(workspace, scope, opinion, state="ACCEPT", conditions=[condition])

    monkeypatch.setattr(tx, "_recover_prepared_transactions_unlocked", original_recovery)
    journals = _transaction_journals(workspace)
    assert len(journals) == 1
    raw = journals[0].read_text(encoding="utf-8")
    assert secret_label not in raw
    assert "synthetic-closure" not in raw
    assert "closure_evidence_reference" not in raw

    recovery = tx.recover_governance_transactions(workspace)
    assert recovery["rolled_back"] == 1
    assert _transaction_journals(workspace) == []
    assert list((workspace.root / "governance" / "owner-dispositions").glob("*.json")) == []
