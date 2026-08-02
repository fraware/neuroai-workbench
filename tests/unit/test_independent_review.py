from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.independent_review import (
    INDEPENDENT_REVIEW_BOUNDARY,
    _hash_record,
    load_independent_review_dispositions,
    record_independent_review_disposition,
    scope_sha256_for_path,
    summarize_independent_review_acceptance,
    verify_independent_review_dispositions,
)
from neuroai_workbench.util import atomic_write_json
from neuroai_workbench.workspace import Workspace


def _reviewer_claim(name: str = "Independent reviewer") -> dict[str, str]:
    return {
        "name_or_role": name,
        "organization": "Example review body",
        "accountability_state": "CLAIMED_LOCAL_IDENTITY",
        "independence_statement": "No material conflict with the frozen review scope.",
        "conflict_of_interest_disclosure": "None declared.",
    }


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace.initialize(tmp_path / "workspace")


def _scope_artifact(tmp_path: Path) -> Path:
    path = tmp_path / "scope.json"
    atomic_write_json(path, {"release": "v0.3.0.dev0", "boundary": "synthetic review scope"})
    return path


def test_independent_review_disposition_is_append_only_and_non_authorizing(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    scope = _scope_artifact(tmp_path)
    scope_digest = scope_sha256_for_path(scope)

    result = record_independent_review_disposition(
        workspace,
        "SECURITY",
        scope_label="v0.3.0.dev0 release candidate",
        scope_sha256=scope_digest,
        disposition="ACCEPTED_WITH_CONDITIONS",
        reviewer_claim=_reviewer_claim(),
        rationale="Scope reviewed; residual items tracked.",
        conditions=["Close SEC-014 before institutional pilot."],
        findings_register_ref="FINDINGS-SECURITY-2026-001",
    )
    record = result["disposition"]
    assert record["release_authorization_performed"] is False
    assert record["boundary"] == INDEPENDENT_REVIEW_BOUNDARY
    assert record["disposition_sha256"] == _hash_record(record)

    verification = verify_independent_review_dispositions(workspace)
    assert verification["valid"] is True
    assert verification["release_authorization_performed"] is False
    assert verification["counts"]["dispositions"] == 1

    summary = summarize_independent_review_acceptance(workspace)
    assert summary["release_authorization_performed"] is False
    assert summary["institutional_pilot_readiness_established"] is False
    assert summary["tracks_complete"] is False
    assert "SECURITY" in summary["latest_by_track"]
    assert "METHODOLOGY" in summary["blocking_tracks"]

    path = Path(result["path"])
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["disposition_id"] == record["disposition_id"]


def test_disposition_requires_conditions_for_accepted_with_conditions(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    scope_digest = scope_sha256_for_path(_scope_artifact(tmp_path))
    with pytest.raises(ValueError, match="requires at least one condition"):
        record_independent_review_disposition(
            workspace,
            "DOMAIN",
            scope_label="scope",
            scope_sha256=scope_digest,
            disposition="ACCEPTED_WITH_CONDITIONS",
            reviewer_claim=_reviewer_claim(),
            rationale="Missing conditions.",
        )


def test_all_review_tracks_can_be_recorded(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    scope_digest = scope_sha256_for_path(_scope_artifact(tmp_path))
    tracks = (
        "SECURITY",
        "METHODOLOGY",
        "DATA_GOVERNANCE",
        "ACCESSIBILITY",
        "DOMAIN",
        "AFFECTED_COMMUNITY",
    )
    for track in tracks:
        record_independent_review_disposition(
            workspace,
            track,
            scope_label="v0.3.0.dev0 release candidate",
            scope_sha256=scope_digest,
            disposition="ACCEPTED",
            reviewer_claim=_reviewer_claim(track),
            rationale=f"{track} review complete for frozen scope.",
        )

    records = load_independent_review_dispositions(workspace)
    assert len(records) == 6
    summary = summarize_independent_review_acceptance(workspace)
    assert summary["tracks_complete"] is True
    assert summary["blocking_tracks"] == []
    assert summary["release_authorization_performed"] is False


def test_verification_detects_tampered_disposition(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    scope_digest = scope_sha256_for_path(_scope_artifact(tmp_path))
    result = record_independent_review_disposition(
        workspace,
        "METHODOLOGY",
        scope_label="scope",
        scope_sha256=scope_digest,
        disposition="ACCEPTED",
        reviewer_claim=_reviewer_claim(),
        rationale="Methodology review complete.",
    )
    path = Path(result["path"])
    record = json.loads(path.read_text(encoding="utf-8"))
    record["rationale"] = "Tampered rationale"
    path.write_text(json.dumps(record), encoding="utf-8")

    report = verify_independent_review_dispositions(workspace)
    assert report["valid"] is False
    assert any("hash mismatch" in error for error in report["errors"])


def test_verification_rejects_release_authorization_flag(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    scope_digest = scope_sha256_for_path(_scope_artifact(tmp_path))
    result = record_independent_review_disposition(
        workspace,
        "SECURITY",
        scope_label="scope",
        scope_sha256=scope_digest,
        disposition="ACCEPTED",
        reviewer_claim=_reviewer_claim(),
        rationale="Security review complete.",
    )
    path = Path(result["path"])
    record = json.loads(path.read_text(encoding="utf-8"))
    record["release_authorization_performed"] = True
    record["disposition_sha256"] = _hash_record(record)
    path.write_text(json.dumps(record), encoding="utf-8")

    report = verify_independent_review_dispositions(workspace)
    assert report["valid"] is False
    assert any("release authorization must remain false" in error for error in report["errors"])


def test_existing_disposition_path_is_not_overwritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class _FixedUUID:
        hex = "a" * 32

    monkeypatch.setattr("neuroai_workbench.independent_review.uuid4", lambda: _FixedUUID())
    workspace = _workspace(tmp_path)
    scope_digest = scope_sha256_for_path(_scope_artifact(tmp_path))
    record_independent_review_disposition(
        workspace,
        "DATA_GOVERNANCE",
        scope_label="scope",
        scope_sha256=scope_digest,
        disposition="ACCEPTED",
        reviewer_claim=_reviewer_claim(),
        rationale="Data governance review complete.",
    )
    with pytest.raises(ValueError, match="already exists"):
        record_independent_review_disposition(
            workspace,
            "DATA_GOVERNANCE",
            scope_label="scope",
            scope_sha256=scope_digest,
            disposition="ACCEPTED",
            reviewer_claim=_reviewer_claim(),
            rationale="Second write must be refused.",
        )


def test_scope_sha256_for_path_requires_existing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        scope_sha256_for_path(tmp_path / "missing.json")


def test_rejected_track_blocks_acceptance_summary(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    scope_digest = scope_sha256_for_path(_scope_artifact(tmp_path))
    record_independent_review_disposition(
        workspace,
        "SECURITY",
        scope_label="scope",
        scope_sha256=scope_digest,
        disposition="REJECTED",
        reviewer_claim=_reviewer_claim(),
        rationale="Critical findings remain open.",
        unresolved_risks=["Unbounded network exposure in custom deployment."],
    )
    summary = summarize_independent_review_acceptance(workspace)
    assert summary["tracks_complete"] is False
    assert "SECURITY" in summary["blocking_tracks"]


def test_record_rejects_invalid_inputs(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    scope_digest = scope_sha256_for_path(_scope_artifact(tmp_path))
    claim = _reviewer_claim()
    with pytest.raises(ValueError, match="Unsupported independent review track"):
        record_independent_review_disposition(
            workspace, "INVALID", "scope", scope_digest, "ACCEPTED", claim, "rationale"
        )
    with pytest.raises(ValueError, match="Unsupported independent review disposition"):
        record_independent_review_disposition(
            workspace, "SECURITY", "scope", scope_digest, "INVALID", claim, "rationale"
        )
    with pytest.raises(ValueError, match="must not be empty"):
        record_independent_review_disposition(workspace, "SECURITY", "scope", scope_digest, "ACCEPTED", claim, "  ")
    with pytest.raises(ValueError, match="reviewer_claim.name_or_role"):
        record_independent_review_disposition(
            workspace,
            "SECURITY",
            "scope",
            scope_digest,
            "ACCEPTED",
            {"accountability_state": "CLAIMED_LOCAL_IDENTITY", "independence_statement": "indep"},
            "rationale",
        )
    with pytest.raises(ValueError, match="scope_sha256"):
        record_independent_review_disposition(
            workspace, "SECURITY", "scope", "not-a-valid-digest", "ACCEPTED", claim, "rationale"
        )
    with pytest.raises(ValueError, match="reviewer_claim must be an object"):
        record_independent_review_disposition(
            workspace, "SECURITY", "scope", scope_digest, "ACCEPTED", "not-a-object", "rationale"  # type: ignore[arg-type]
        )


def test_verification_detects_duplicate_disposition_id_and_invalid_track(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    scope_digest = scope_sha256_for_path(_scope_artifact(tmp_path))
    result = record_independent_review_disposition(
        workspace,
        "METHODOLOGY",
        scope_label="scope",
        scope_sha256=scope_digest,
        disposition="ACCEPTED",
        reviewer_claim=_reviewer_claim(),
        rationale="Methodology review complete.",
    )
    duplicate = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    duplicate["disposition_id"] = "IRD-" + "c" * 32
    duplicate["disposition_sha256"] = _hash_record(duplicate)
    root = workspace.root / "independent_reviews" / "dispositions"
    atomic_write_json(root / f"{duplicate['disposition_id']}.json", duplicate)

    invalid_track = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    invalid_track["review_track"] = "INVALID"
    invalid_track["disposition_sha256"] = _hash_record(invalid_track)
    Path(result["path"]).write_text(json.dumps(invalid_track), encoding="utf-8")

    report = verify_independent_review_dispositions(workspace)
    assert report["valid"] is False
    assert any("unsupported review track" in error for error in report["errors"])


def test_verification_detects_invalid_event_chain(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    scope_digest = scope_sha256_for_path(_scope_artifact(tmp_path))
    record_independent_review_disposition(
        workspace,
        "SECURITY",
        scope_label="scope",
        scope_sha256=scope_digest,
        disposition="ACCEPTED",
        reviewer_claim=_reviewer_claim(),
        rationale="Security review complete.",
    )
    events_path = workspace.root / "events.jsonl"
    line = events_path.read_text(encoding="utf-8").strip().splitlines()[0]
    event = json.loads(line)
    event["actor"] = "tampered"
    events_path.write_text(json.dumps(event) + "\n", encoding="utf-8")
    report = verify_independent_review_dispositions(workspace)
    assert report["valid"] is False
    assert any("event chain:" in error for error in report["errors"])


def test_verification_detects_duplicate_and_invalid_schema(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    scope_digest = scope_sha256_for_path(_scope_artifact(tmp_path))
    result = record_independent_review_disposition(
        workspace,
        "ACCESSIBILITY",
        scope_label="scope",
        scope_sha256=scope_digest,
        disposition="DEFERRED",
        reviewer_claim=_reviewer_claim(),
        rationale="Representative-user testing pending.",
    )
    root = workspace.root / "independent_reviews" / "dispositions"
    duplicate = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    duplicate_id = result["disposition"]["disposition_id"]
    atomic_write_json(root / f"IRD-{'d' * 32}.json", duplicate)

    path = Path(result["path"])
    invalid = json.loads(path.read_text(encoding="utf-8"))
    invalid["disposition"] = "ACCEPTED_WITH_CONDITIONS"
    invalid.pop("conditions", None)
    invalid["disposition_sha256"] = _hash_record(invalid)
    path.write_text(json.dumps(invalid), encoding="utf-8")

    report = verify_independent_review_dispositions(workspace)
    assert report["valid"] is False
    assert any("conditions required" in error for error in report["errors"])
    assert any(f"disposition {duplicate_id}: duplicate disposition_id" in error for error in report["errors"])


def test_summarize_reports_integrity_invalid_when_verification_fails(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    scope_digest = scope_sha256_for_path(_scope_artifact(tmp_path))
    result = record_independent_review_disposition(
        workspace,
        "DOMAIN",
        scope_label="scope",
        scope_sha256=scope_digest,
        disposition="ACCEPTED",
        reviewer_claim=_reviewer_claim(),
        rationale="Domain review complete.",
    )
    path = Path(result["path"])
    record = json.loads(path.read_text(encoding="utf-8"))
    record["rationale"] = "Tampered"
    path.write_text(json.dumps(record), encoding="utf-8")
    summary = summarize_independent_review_acceptance(workspace)
    assert summary["integrity_valid"] is False
