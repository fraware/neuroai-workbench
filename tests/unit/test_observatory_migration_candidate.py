from __future__ import annotations

import json

import pytest

from neuroai_workbench.observatory_migration_candidate import (
    MIGRATION_CANDIDATE_BOUNDARY,
    ObservatoryMigrationCandidateError,
    build_predecessor_migration_candidate,
    verify_predecessor_migration_candidate,
    write_predecessor_migration_candidate_package,
)
from neuroai_workbench.util import canonical_json_bytes, sha256_bytes


def _organization(org_id: str = "ORG-1", name: str = "Science Corporation") -> dict:
    return {
        "organization_id": org_id,
        "canonical_name": name,
        "aliases": [],
        "organization_type": "COMPANY",
        "roles": ["SYSTEM_DEVELOPER"],
        "current_status": "CURRENT",
        "verification_state": "CURRENT_VERIFIED",
        "evidence_state": "OFFICIAL_CURRENT_REPRESENTATION",
        "official_url": "https://example.test/",
        "source_ids": ["SRC-1"],
        "last_verified": "2026-07-29",
        "claim_boundary": "Presence only.",
    }


def _legacy() -> dict:
    return {
        "organization_id": "ORG-LEGACY",
        "canonical_name": "Legacy endpoint",
        "aliases": [],
        "organization_type": "LEGACY_STUB",
        "roles": ["LEGACY_RELATIONSHIP_ENDPOINT"],
        "current_status": "ACTIVE_OR_CURRENTLY_REPRESENTED",
        "verification_state": "LEGACY_ONLY",
        "evidence_state": "LEGACY_UNVERIFIED",
        "source_ids": [],
        "last_verified": None,
    }


def _source(source_id: str = "SRC-1") -> dict:
    return {
        "source_id": source_id,
        "title": "Official source",
        "publisher": "Publisher",
        "url": f"https://example.test/{source_id}",
        "source_class": "OFFICIAL_PAGE",
        "retrieved": "2026-07-29",
        "verification_state": "CURRENT_VERIFIED",
        "evidence_state": "CURRENT_SOURCE_RETRIEVED",
        "supports": "Bounded source statement",
        "claim_boundary": "Retrieval is not substantive truth.",
        "legacy_source_ids": [],
    }


def _new_source(source_id: str = "SRC-16-1") -> dict:
    return {
        "source_id": source_id,
        "title": "Announcement",
        "publisher": "Publisher",
        "url": f"https://example.test/{source_id}",
        "published": "2026-07-22",
        "retrieved": "2026-07-29T12:38:00Z",
        "source_class": "OFFICIAL_COMPANY_ANNOUNCEMENT",
        "evidence_state": "COMPANY_ANNOUNCEMENT",
        "supports": "Bounded source statement",
        "claim_boundary": "No broader inference.",
    }


def _check(source_id: str = "SRC-16-1") -> dict:
    return {
        "check_id": "CHK-1",
        "source_id": source_id,
        "retrieved": "2026-07-29T12:38:00Z",
        "retrieval_outcome": "SUCCESS_VIA_WEB_RESEARCH",
        "baseline_match": "NEW_SOURCE_OR_BACKFILL",
        "page_content_hash": "NOT_AVAILABLE_FROM_WEB_RESEARCH_INTERFACE",
        "metadata_digest": "a" * 64,
    }


def _resolution() -> dict:
    return {
        "resolution_id": "RES-1",
        "organization_id": "ORG-1",
        "name_before": "Science Corporation",
        "verification_before": "CURRENT_PARTIAL",
        "disposition": "CURRENT_VERIFIED",
        "verification_after": "CURRENT_VERIFIED",
        "source_ids": ["SRC-1"],
        "rationale": "Current identity verified within bounded source universe.",
        "effective_date": "2026-07-29",
    }


def _regional() -> dict:
    return {
        "regional_record_id": "REG-1",
        "organization_id": "ORG-1",
        "canonical_name": "Science Corporation",
        "unesco_region": "Europe and North America",
        "country_or_scope": "United States",
        "action": "ADD",
        "inclusion_rule": "Official source in frozen regional universe.",
        "verification_state": "CURRENT_VERIFIED",
        "source_ids": ["SRC-1"],
        "claim_boundary": "Acquisition coverage only.",
    }


def _capital_event(date: str | None = "2026-03-05") -> dict:
    return {
        "event_id": "CAP-1",
        "date": date,
        "event_type": "EQUITY_FINANCING",
        "subject": "Science Corporation",
        "counterparties": ["Investor A"],
        "amount": 230000000,
        "currency": "USD",
        "amount_state": "ANNOUNCED_EXACT",
        "ownership_effect": "UNRESOLVED",
        "source_ids": ["SRC-1"],
        "evidence_state": "COMPANY_ANNOUNCEMENT",
        "boundary": "Company-announced financing; no valuation or control inference.",
    }


def _change_candidate() -> dict:
    return {
        "candidate_id": "CAND-1",
        "event_date": "2026-07-22",
        "discovery_class": "PRE_CUTOFF_EVIDENCE_DISCOVERED_AFTER_FREEZE",
        "change_class": "REGULATORY_AND_MARKET_STATE_CHANGE",
        "subject": "Science Corporation",
        "summary": "Bounded update.",
        "source_ids": ["SRC-16-1"],
        "materiality": "HIGH",
        "adjudication": "ACCEPT_WITH_EVIDENCE_BOUNDARY",
        "reopening": "SYSTEM_RECORD_REOPEN_REQUIRED",
    }


def _inputs() -> tuple[dict, dict]:
    v14 = {
        "organizations": [_organization(), _legacy()],
        "organization_resolution": [_resolution()],
        "regional_expansion": [_regional()],
        "sources": [_source()],
        "capital_and_ownership_events": [_capital_event()],
    }
    v16 = {
        "new_sources": [_new_source()],
        "source_checks": [_check()],
        "change_candidates": [_change_candidate()],
    }
    return v14, v16


def test_candidate_adds_complete_safe_families_to_core() -> None:
    v14, v16 = _inputs()
    result = build_predecessor_migration_candidate(v14_release=v14, v16_refresh=v16)

    assert result["mechanical_verification"] == "PASS"
    assert result["state"] == "NONCANONICAL_CANDIDATE"
    assert result["release_authorized"] is False
    assert result["native_v2_materialization_complete"] is False
    assert result["counts"]["native_entities"] == 1
    assert result["counts"]["native_sources"] == 2
    assert result["counts"]["preserved_identity_resolution_history"] == 1
    assert result["counts"]["preserved_regional_expansion_history"] == 1
    assert result["counts"]["governed_predecessor_history_records"] == 2
    assert result["counts"]["native_capital_events"] == 1
    assert result["counts"]["native_change_candidates"] == 1
    assert result["counts"]["native_candidate_objects"] == 5
    for family in (
        "V14.organization_resolution",
        "V14.regional_expansion",
        "V14.capital_and_ownership_events",
        "V16.change_candidates",
    ):
        assert family not in result["remaining_unmaterialized_families"]
    assert result["boundaries"]["candidate"] == MIGRATION_CANDIDATE_BOUNDARY
    assert verify_predecessor_migration_candidate(result)["valid"] is True


def test_candidate_verifier_detects_history_substitution() -> None:
    v14, v16 = _inputs()
    result = build_predecessor_migration_candidate(v14_release=v14, v16_refresh=v16)
    result["identity_resolution_history"]["records"][0]["predecessor_record"]["verification_after"] = (
        "CURRENT_PARTIAL"
    )
    report = verify_predecessor_migration_candidate(result)
    assert report["valid"] is False
    assert any("predecessor_record_sha256 mismatch" in error for error in report["errors"])


def test_candidate_verifier_detects_coordinated_event_subject_substitution() -> None:
    v14, v16 = _inputs()
    v14["organizations"].append(_organization("ORG-2", "Other Organization"))
    result = build_predecessor_migration_candidate(v14_release=v14, v16_refresh=v16)

    event = result["capital_event_migration"]["events"][0]
    trace = result["capital_event_migration"]["predecessor_traces"][0]
    event["subject"]["entity_id"] = "ORG-2"
    trace["subject_entity_id"] = "ORG-2"

    report = verify_predecessor_migration_candidate(result)
    assert report["valid"] is False
    assert any("exact predecessor canonical label" in error for error in report["errors"])


def test_candidate_verifier_detects_event_temporal_invention() -> None:
    v14, v16 = _inputs()
    v14["capital_and_ownership_events"][0]["date"] = None
    result = build_predecessor_migration_candidate(v14_release=v14, v16_refresh=v16)
    result["capital_event_migration"]["events"][0]["occurred_at"] = {
        "value": "2026-01-01",
        "precision": "DATE",
        "boundary": "fabricated",
    }

    report = verify_predecessor_migration_candidate(result)
    assert report["valid"] is False
    assert any("null predecessor date must remain absent" in error for error in report["errors"])


def test_candidate_verifier_detects_missing_event_source() -> None:
    v14, v16 = _inputs()
    result = build_predecessor_migration_candidate(v14_release=v14, v16_refresh=v16)
    result["capital_event_migration"]["events"][0]["source_ids"] = ["SRC-MISSING"]

    report = verify_predecessor_migration_candidate(result)
    assert report["valid"] is False
    assert any("source_ids binding mismatch" in error or "references missing Sources" in error for error in report["errors"])


def test_candidate_verifier_detects_change_candidate_payload_tampering() -> None:
    v14, v16 = _inputs()
    result = build_predecessor_migration_candidate(v14_release=v14, v16_refresh=v16)
    result["change_candidate_migration"]["candidates"][0]["payload"]["summary"] = "Substituted"

    report = verify_predecessor_migration_candidate(result)
    assert report["valid"] is False
    assert any("Candidate.payload must equal exact predecessor record" in error for error in report["errors"])


def test_candidate_package_is_deterministic_and_manifest_bound(tmp_path) -> None:
    v14, v16 = _inputs()
    result = build_predecessor_migration_candidate(v14_release=v14, v16_refresh=v16)
    first = write_predecessor_migration_candidate_package(
        result,
        tmp_path / "first",
        v14_input_sha256="a" * 64,
        v16_input_sha256="b" * 64,
        producer_commit="c" * 40,
        runtime_execution_pin="d" * 40,
        s2_predecessor_commit="e" * 40,
    )
    second = write_predecessor_migration_candidate_package(
        result,
        tmp_path / "second",
        v14_input_sha256="a" * 64,
        v16_input_sha256="b" * 64,
        producer_commit="c" * 40,
        runtime_execution_pin="d" * 40,
        s2_predecessor_commit="e" * 40,
    )

    assert first == second
    for filename in (
        "entities.jsonl",
        "sources.jsonl",
        "events.jsonl",
        "candidates.jsonl",
        "entity-predecessor-traces.jsonl",
        "source-predecessor-traces.jsonl",
        "event-predecessor-traces.jsonl",
        "candidate-predecessor-traces.jsonl",
        "preserved-organizations.jsonl",
        "predecessor-observation-evidence.jsonl",
        "identity-resolution-history.jsonl",
        "regional-expansion-history.jsonl",
        "descriptor.json",
        "manifest.json",
    ):
        assert (tmp_path / "first" / filename).read_bytes() == (tmp_path / "second" / filename).read_bytes()

    manifest = json.loads((tmp_path / "first" / "manifest.json").read_text(encoding="utf-8"))
    controlled = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    assert manifest["manifest_sha256"] == sha256_bytes(canonical_json_bytes(controlled))
    assert manifest["release_authorized"] is False
    assert manifest["native_v2_materialization_complete"] is False


def test_candidate_package_refuses_authority_upgrade(tmp_path) -> None:
    v14, v16 = _inputs()
    result = build_predecessor_migration_candidate(v14_release=v14, v16_refresh=v16)
    result["release_authorized"] = True
    with pytest.raises(ObservatoryMigrationCandidateError, match="invalid migration candidate"):
        write_predecessor_migration_candidate_package(
            result,
            tmp_path / "bad",
            v14_input_sha256="a" * 64,
            v16_input_sha256="b" * 64,
            producer_commit="c" * 40,
            runtime_execution_pin="d" * 40,
            s2_predecessor_commit="e" * 40,
        )
