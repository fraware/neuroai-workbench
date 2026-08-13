from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

import neuroai_workbench.governance_release as release_mod
from neuroai_workbench.governance_opinions import REVIEW_TRACKS, record_governance_reviewer_opinion
from neuroai_workbench.governance_release import (
    REAL_AUTHORITY_ACCOUNTABILITY_STATE,
    REAL_GOVERNANCE_EXECUTION_MODE,
    load_governance_release_decisions,
    record_release_authorization,
    record_release_publication,
    verify_governance_release_decisions,
)
from neuroai_workbench.governance_scope import record_governance_scope_manifest, scope_object_for_path
from neuroai_workbench.governance_transactions import append_governance_record_locked as real_append_governance_record_locked
from neuroai_workbench.successor import generate_from_observatory_release
from neuroai_workbench.util import atomic_write_json
from neuroai_workbench.workspace import Workspace

ROOT = Path(__file__).resolve().parents[2]
SUCCESSOR = ROOT / "examples" / "observatory" / "canonical_successor_snapshot_v1.7.json"
PRODUCTS = [{"product_id": "TEST-FIXTURE-PRODUCT", "sha256": "a" * 64}]


def _workspace_scope_candidate(tmp_path: Path) -> tuple[Workspace, dict[str, Any], dict[str, Any]]:
    workspace = Workspace.initialize(tmp_path / "workspace")
    public = tmp_path / "public"
    generated = tmp_path / "generated"
    archive = tmp_path / "archive"
    for root in (public, generated, archive):
        root.mkdir()
    fixture_paths = {
        "predecessor": archive / "predecessor.json",
        "candidate": generated / "candidate.json",
        "delta": generated / "delta.json",
        "reopening": generated / "reopening.json",
        "products": generated / "products.json",
        "claims": public / "claims.json",
    }
    for label, path in fixture_paths.items():
        atomic_write_json(path, {"test_fixture_only": label})
    objects = [
        scope_object_for_path(
            role="PREDECESSOR_RELEASE",
            label="TEST FIXTURE predecessor",
            object_type="RELEASE",
            path=fixture_paths["predecessor"],
            storage_boundary="ARCHIVE",
            boundary_root=archive,
        ),
        scope_object_for_path(
            role="SUCCESSOR_CANDIDATE",
            label="TEST FIXTURE candidate",
            object_type="SUCCESSOR_CANDIDATE",
            path=fixture_paths["candidate"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="DELTA",
            label="TEST FIXTURE delta",
            object_type="DELTA",
            path=fixture_paths["delta"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="REOPENING_REGISTER",
            label="TEST FIXTURE reopening",
            object_type="REOPENING_REGISTER",
            path=fixture_paths["reopening"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="PRODUCT_MANIFEST",
            label="TEST FIXTURE products",
            object_type="PRODUCT_MANIFEST",
            path=fixture_paths["products"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="WITHHELD_CLAIMS",
            label="TEST FIXTURE withheld claims",
            object_type="CLAIM_SET",
            path=fixture_paths["claims"],
            storage_boundary="PUBLIC_GIT",
            boundary_root=public,
        ),
    ]
    scope = record_governance_scope_manifest(
        workspace,
        scope_label="TEST FIXTURE ONLY - release transaction integration",
        objects=objects,
        boundary_roots={"PUBLIC_GIT": public, "GENERATED_OUTPUT": generated, "ARCHIVE": archive},
        actor="test-fixture",
    )["manifest"]
    for track in sorted(REVIEW_TRACKS):
        for suffix in ("a", "b"):
            record_governance_reviewer_opinion(
                workspace,
                scope_id=scope["scope_id"],
                scope_sha256=scope["manifest_sha256"],
                review_track=track,
                opinion_state="SUPPORT",
                reviewer_claim={
                    "reviewer_key": f"test-{track.lower()}-{suffix}",
                    "name_or_role": f"TEST FIXTURE ONLY reviewer {track} {suffix}",
                    "organization": f"TEST FIXTURE ONLY {track} org {suffix}",
                    "accountability_state": "CLAIMED_HUMAN_REVIEWER",
                    "independence_statement": "TEST FIXTURE ONLY claimed independence; not authenticated.",
                    "conflict_of_interest_disclosure": "NO_CONFLICT_DECLARED: TEST FIXTURE ONLY",
                },
                rationale="TEST FIXTURE ONLY support opinion.",
                actor="test-fixture",
            )
    candidate = generate_from_observatory_release(
        SUCCESSOR,
        version="v1.8-release-transaction-fixture",
        actor="test-fixture",
    )
    return workspace, scope, candidate


def _authority_claim() -> dict[str, str]:
    return {
        "name_or_role": "TEST FIXTURE ONLY release authority role",
        "organization": "TEST FIXTURE ONLY organization",
        "authority_basis": "TEST FIXTURE ONLY structural path verification",
        "accountability_state": REAL_AUTHORITY_ACCOUNTABILITY_STATE,
        "execution_mode": REAL_GOVERNANCE_EXECUTION_MODE,
        "authority_evidence_reference": "protected-ref:test-fixture-only/release-authority",
        "authority_evidence_sha256": "b" * 64,
    }


def _authorization_kwargs(scope: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate": candidate,
        "scope_id": scope["scope_id"],
        "scope_sha256": scope["manifest_sha256"],
        "products": PRODUCTS,
        "authority_claim": _authority_claim(),
        "actor": "test-fixture",
    }


def test_authorization_crash_after_record_before_event_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, scope, candidate = _workspace_scope_candidate(tmp_path)

    def injected_append(*args: Any, **kwargs: Any) -> dict[str, Any]:
        def hook(phase: str) -> None:
            if phase == "AFTER_RECORD_WRITE":
                raise RuntimeError("TEST FIXTURE injected pre-event interruption")

        kwargs["phase_hook"] = hook
        return real_append_governance_record_locked(*args, **kwargs)

    monkeypatch.setattr(release_mod, "append_governance_record_locked", injected_append)
    with pytest.raises(RuntimeError, match="pre-event interruption"):
        record_release_authorization(workspace, **_authorization_kwargs(scope, candidate))

    assert load_governance_release_decisions(workspace) == []
    assert list((workspace.root / "governance" / "transactions").glob("*.json")) == []
    assert verify_governance_release_decisions(workspace)["valid"] is True


def test_authorization_failure_after_commit_event_remains_committed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, scope, candidate = _workspace_scope_candidate(tmp_path)

    def injected_append(*args: Any, **kwargs: Any) -> dict[str, Any]:
        def hook(phase: str) -> None:
            if phase == "AFTER_EVENT_APPEND":
                raise RuntimeError("TEST FIXTURE injected post-event interruption")

        kwargs["phase_hook"] = hook
        return real_append_governance_record_locked(*args, **kwargs)

    monkeypatch.setattr(release_mod, "append_governance_record_locked", injected_append)
    with pytest.raises(RuntimeError, match="post-event interruption"):
        record_release_authorization(workspace, **_authorization_kwargs(scope, candidate))

    decisions = load_governance_release_decisions(workspace)
    assert len(decisions) == 1
    assert decisions[0]["decision_state"] == "AUTHORIZED"
    assert list((workspace.root / "governance" / "transactions").glob("*.json")) == []
    assert verify_governance_release_decisions(workspace)["valid"] is True


def test_two_concurrent_authorization_attempts_produce_exactly_one_commit(tmp_path: Path) -> None:
    workspace, scope, candidate = _workspace_scope_candidate(tmp_path)
    kwargs = _authorization_kwargs(scope, candidate)

    def attempt() -> str:
        try:
            return str(record_release_authorization(workspace, **kwargs)["decision"]["decision_id"])
        except ValueError as exc:
            return f"ERROR:{exc}"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: attempt(), range(2)))

    committed = [result for result in results if not result.startswith("ERROR:")]
    rejected = [result for result in results if result.startswith("ERROR:")]
    assert len(committed) == 1
    assert len(rejected) == 1
    assert "already has an authorization decision" in rejected[0]
    report = verify_governance_release_decisions(workspace)
    assert report["valid"] is True
    assert report["counts"]["authorizations"] == 1


def test_publication_post_event_interruption_preserves_exact_committed_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, scope, candidate = _workspace_scope_candidate(tmp_path)
    authorization = record_release_authorization(
        workspace,
        **_authorization_kwargs(scope, candidate),
    )["decision"]

    def injected_append(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("event_action") == "GOVERNANCE_RELEASE_PUBLICATION_RECORDED":
            def hook(phase: str) -> None:
                if phase == "AFTER_EVENT_APPEND":
                    raise RuntimeError("TEST FIXTURE publication post-event interruption")

            kwargs["phase_hook"] = hook
        return real_append_governance_record_locked(*args, **kwargs)

    monkeypatch.setattr(release_mod, "append_governance_record_locked", injected_append)
    with pytest.raises(RuntimeError, match="publication post-event interruption"):
        record_release_publication(
            workspace,
            candidate=candidate,
            scope_id=scope["scope_id"],
            scope_sha256=scope["manifest_sha256"],
            products=PRODUCTS,
            authorization_decision_id=authorization["decision_id"],
            authority_claim=_authority_claim(),
            publication_evidence={
                "reference": "public-ref:test-fixture-only/publication",
                "sha256": "c" * 64,
            },
            actor="test-fixture",
        )

    report = verify_governance_release_decisions(workspace)
    assert report["valid"] is True
    assert report["counts"] == {"decisions": 2, "authorizations": 1, "publications": 1}
