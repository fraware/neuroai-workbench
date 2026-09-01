from __future__ import annotations

from neuroai_workbench.observatory_migration_candidate_delta import (
    DELTA16_RESIDUAL_FAMILIES,
    build_predecessor_migration_candidate_with_delta,
    verify_predecessor_migration_candidate_with_delta,
)


def _organization(org_id: str, name: str) -> dict:
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


def _source(source_id: str, *, published: str | None = None) -> dict:
    record = {
        "source_id": source_id,
        "title": "Source",
        "publisher": "Publisher",
        "url": f"https://example.test/{source_id}",
        "source_class": "OFFICIAL_PAGE",
        "retrieved": "2026-07-29T12:38:00Z",
        "evidence_state": "SOURCE_STATED",
        "supports": "Bounded statement",
        "claim_boundary": "Retrieval is not substantive truth.",
    }
    if published is not None:
        record["published"] = published
    return record


def _inputs() -> tuple[dict, dict, dict]:
    v14 = {
        "organizations": [
            _organization("ORG-SCI", "Science Corporation"),
            _organization("ORG-SYN", "Synchron"),
        ],
        "sources": [_source("SRC-1")],
        "capital_and_ownership_events": [
            {
                "event_id": "CAP-14-1",
                "date": "2026",
                "event_type": "FINANCING",
                "subject": "Science Corporation",
                "counterparties": [],
                "source_ids": ["SRC-1"],
                "evidence_state": "COMPANY_ANNOUNCEMENT",
                "boundary": "Bounded event.",
            }
        ],
        "organization_resolution": [],
        "regional_expansion": [],
    }
    v16 = {
        "new_sources": [_source("SRC-16-1", published="2026-07-22")],
        "source_checks": [
            {
                "check_id": "CHK-1",
                "source_id": "SRC-16-1",
                "retrieved": "2026-07-29T12:38:00Z",
                "retrieval_outcome": "SUCCESS_VIA_WEB_RESEARCH",
                "baseline_match": "NEW_SOURCE_OR_BACKFILL",
                "page_content_hash": "NOT_AVAILABLE_FROM_WEB_RESEARCH_INTERFACE",
                "metadata_digest": "a" * 64,
            }
        ],
        "change_candidates": [
            {
                "candidate_id": "CAND-1",
                "event_date": "2026-07-22",
                "discovery_class": "HISTORICAL_BACKFILL",
                "change_class": "CAPITAL_AND_CONTINUITY_CHANGE",
                "subject": "Science Corporation",
                "summary": "Financing",
                "source_ids": ["SRC-16-1"],
                "materiality": "MEDIUM",
                "adjudication": "ACCEPT_AS_COMPANY_ANNOUNCED_EVENT",
                "reopening": "ORGANIZATION_AND_CAPITAL_RECORD_UPDATE",
            }
        ],
    }
    delta16 = {
        "capital_and_ownership_events": [
            {
                "event_id": "CAP-16-1",
                "date": "2026-03-05",
                "event_type": "EQUITY_FINANCING",
                "subject": "Science Corporation",
                "amount": 230000000,
                "currency": "USD",
                "source_ids": ["SRC-16-1"],
                "boundary": "Company-announced financing; no valuation or control inference.",
            },
            {
                "event_id": "CAP-16-2",
                "date": "2025-11-06",
                "event_type": "SERIES_D_FINANCING",
                "subject": "Synchron",
                "amount": 200000000,
                "currency": "USD",
                "source_ids": ["SRC-16-1"],
                "boundary": "Company press release; no authorization inference.",
            },
        ]
    }
    return v14, v16, delta16


def test_delta_extension_adds_complete_family_without_authority_upgrade() -> None:
    v14, v16, delta16 = _inputs()
    result = build_predecessor_migration_candidate_with_delta(
        v14_release=v14,
        v16_refresh=v16,
        delta16=delta16,
    )
    assert result["mechanical_verification"] == "PASS"
    assert result["release_authorized"] is False
    assert result["native_v2_materialization_complete"] is False
    assert result["counts"]["native_delta16_capital_events"] == 2
    assert result["counts"]["native_candidate_objects_with_delta"] == len(result["native_objects"])
    remaining = result["remaining_unmaterialized_families"]
    assert "DELTA16.*" not in remaining
    assert "DELTA16.capital_and_ownership_events" not in remaining
    assert set(DELTA16_RESIDUAL_FAMILIES).issubset(remaining)
    assert verify_predecessor_migration_candidate_with_delta(result)["valid"] is True


def test_delta_extension_verifier_detects_mapped_event_tampering() -> None:
    v14, v16, delta16 = _inputs()
    result = build_predecessor_migration_candidate_with_delta(
        v14_release=v14,
        v16_refresh=v16,
        delta16=delta16,
    )
    result["delta16_capital_event_migration"]["events"][0]["claim_boundary"] = "Broader claim"
    report = verify_predecessor_migration_candidate_with_delta(result)
    assert report["valid"] is False
    assert any("claim_boundary binding mismatch" in error for error in report["errors"])


def test_delta_extension_verifier_rejects_wildcard_regression() -> None:
    v14, v16, delta16 = _inputs()
    result = build_predecessor_migration_candidate_with_delta(
        v14_release=v14,
        v16_refresh=v16,
        delta16=delta16,
    )
    result["remaining_unmaterialized_families"].append("DELTA16.*")
    report = verify_predecessor_migration_candidate_with_delta(result)
    assert report["valid"] is False
    assert "DELTA16 wildcard remains after partial family materialization" in report["errors"]
