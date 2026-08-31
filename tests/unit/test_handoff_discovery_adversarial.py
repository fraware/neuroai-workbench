"""Adversarial coverage for discovery programme and universe projection."""

from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.collector.adapters.clinicaltrials import ClinicalTrialsGovAdapter
from neuroai_workbench.discovery import (
    DiscoveryError,
    load_first_wave_programmes,
    load_programme,
    load_su_trial_programme,
    programme_maturity,
    run_source_universe,
    validate_programme,
)
from neuroai_workbench.discovery.clinicaltrials import project_search_pages
from neuroai_workbench.discovery.errors import DiscoveryNetworkBlockedError
from neuroai_workbench.discovery.programme import documentation_alias_for
from neuroai_workbench.discovery.store import initialize_discovery_workspace, seed_fixture_queries
from neuroai_workbench.discovery.universe_projection import project_universe_pages


def _study(nct_id: str, title: str, study_type: str = "INTERVENTIONAL") -> dict:
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct_id, "briefTitle": title},
            "statusModule": {
                "overallStatus": "RECRUITING",
                "lastUpdatePostDateStruct": {"date": "2026-08-01"},
                "primaryCompletionDateStruct": {"date": "2027-01"},
                "enrollmentInfo": {"count": 20},
            },
            "designModule": {"studyType": study_type, "phases": ["NA"]},
        }
    }


def test_programme_alias_maturity_and_guards(tmp_path: Path) -> None:
    with pytest.raises(DiscoveryError, match="documentation alias"):
        load_programme("SU-TRIALS")
    with pytest.raises(DiscoveryError, match="Unknown"):
        load_programme("SU-DOES-NOT-EXIST")
    with pytest.raises(DiscoveryError, match="object"):
        validate_programme([])
    with pytest.raises(DiscoveryError, match="invalid"):
        validate_programme({"universe_id": "SU-TRIAL"})

    programmes = load_first_wave_programmes()
    assert len(programmes) == 5
    pubs = load_programme("SU-PUBS")
    assert programme_maturity(pubs) == "OFFLINE_EXECUTABLE"
    assert documentation_alias_for("SU-PUBS") == "SU-PUBLICATIONS"
    scaffold = {"universe_id": "SU-FUTURE", "evaluation": {}}
    assert programme_maturity(scaffold) == "SCAFFOLD_NOT_COMPLETE"
    assert programme_maturity({"universe_id": "SU-TRIAL", "evaluation": {"maturity": "  CUSTOM  "}}) == "CUSTOM"

    with pytest.raises(DiscoveryError, match="pages"):
        run_source_universe(programme=pubs, execution_mode="OFFLINE_FIXTURE", pages=None)
    with pytest.raises(DiscoveryNetworkBlockedError):
        run_source_universe(
            programme=pubs,
            execution_mode="AUTHORIZED_NETWORK",
            pages=[{"payload": {"records": [{"identity": "10.1000/x", "title": "t"}]}}],
        )

    pages = [
        {
            "payload": {
                "records": [
                    {"identity": "10.1000/neuroai.ok", "title": "Ok", "url": "https://doi.org/10.1000/neuroai.ok"}
                ],
                "total_count": 1,
            }
        }
    ]
    initialize_discovery_workspace(tmp_path)
    seed_fixture_queries(tmp_path)
    result = run_source_universe(
        programme=pubs,
        execution_mode="OFFLINE_FIXTURE",
        pages=pages,
        workspace=tmp_path,
        known_identities={"10.1000/neuroai.ok": "SRC-PUB-EXISTING"},
    )
    assert result["coverage"]["known_identity_duplicate_count"] == 1
    assert result["workflow"]["run"]["automatic_registry_mutation_performed"] is False

    bad_identity = run_source_universe(
        programme=pubs,
        execution_mode="OFFLINE_REPLAY",
        pages=[{"payload": {"records": [{"identity": "NOT-A-DOI", "title": "x"}]}}],
    )
    assert bad_identity["coverage"]["included_candidate_count"] == 0
    assert any(item["failure_class"] == "INVALID_IDENTITY" for item in bad_identity["coverage"]["failures"])


def test_offline_universe_rejects_authorized_network_even_when_gate_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from neuroai_workbench.discovery import boundary as discovery_boundary

    monkeypatch.setenv(discovery_boundary.DISCOVERY_NETWORK_ENV, "1")
    pubs = load_programme("SU-PUBS")
    with pytest.raises(DiscoveryError, match="OFFLINE_FIXTURE and OFFLINE_REPLAY only"):
        run_source_universe(
            programme=pubs,
            execution_mode="AUTHORIZED_NETWORK",
            pages=[{"payload": {"records": [{"identity": "10.1000/x", "title": "t"}]}}],
        )


def test_universe_projection_fail_closed_paths() -> None:
    pattern = r"^10\.\S+$"
    with pytest.raises(DiscoveryError, match="No offline projection"):
        project_universe_pages(
            universe_id="SU-UNKNOWN",
            query_id="Q",
            query_text="q",
            pages=[{"payload": {"records": []}}],
            identity_pattern=pattern,
        )
    with pytest.raises(DiscoveryError, match="at least one"):
        project_universe_pages(
            universe_id="SU-PUBS",
            query_id="Q",
            query_text="q",
            pages=[],
            identity_pattern=pattern,
        )
    with pytest.raises(DiscoveryError, match="page must be an object"):
        project_universe_pages(
            universe_id="SU-PUBS",
            query_id="Q",
            query_text="q",
            pages=["bad"],  # type: ignore[list-item]
            identity_pattern=pattern,
        )
    with pytest.raises(DiscoveryError, match="payload must be an object"):
        project_universe_pages(
            universe_id="SU-PUBS",
            query_id="Q",
            query_text="q",
            pages=[{"payload": []}],
            identity_pattern=pattern,
        )
    with pytest.raises(DiscoveryError, match="records/items"):
        project_universe_pages(
            universe_id="SU-PUBS",
            query_id="Q",
            query_text="q",
            pages=[{"payload": {"records": "x"}}],
            identity_pattern=pattern,
        )
    with pytest.raises(DiscoveryError, match="next_page_token"):
        project_universe_pages(
            universe_id="SU-PUBS",
            query_id="Q",
            query_text="q",
            pages=[{"payload": {"records": [], "next_page_token": " "}}],
            identity_pattern=pattern,
        )
    with pytest.raises(DiscoveryError, match="total_count"):
        project_universe_pages(
            universe_id="SU-PUBS",
            query_id="Q",
            query_text="q",
            pages=[{"payload": {"records": [], "total_count": -1}}],
            identity_pattern=pattern,
        )
    with pytest.raises(DiscoveryError, match="PAGINATION_SEQUENCE_INVALID"):
        project_universe_pages(
            universe_id="SU-PUBS",
            query_id="Q",
            query_text="q",
            pages=[
                {"payload": {"records": [{"identity": "10.1000/a", "title": "a"}], "total_count": 2}},
                {"payload": {"records": [{"identity": "10.1000/b", "title": "b"}], "total_count": 2}},
            ],
            identity_pattern=pattern,
        )
    with pytest.raises(DiscoveryError, match="CONFLICTING_SAME_IDENTITY"):
        project_universe_pages(
            universe_id="SU-PUBS",
            query_id="Q",
            query_text="q",
            pages=[
                {
                    "payload": {
                        "records": [
                            {"identity": "10.1000/same", "title": "One"},
                            {"identity": "10.1000/same", "title": "Two"},
                        ]
                    }
                }
            ],
            identity_pattern=pattern,
        )

    model = project_universe_pages(
        universe_id="SU-MODEL",
        query_id="Q-MODEL",
        query_text="models",
        pages=[
            {
                "payload": {
                    "records": [
                        {"identity": "org/model-alpha", "title": "Alpha"},
                        {"identity": "org/model-alpha", "title": "Alpha"},
                        {"identity": "org/model-beta", "title": "Beta"},
                    ],
                    "total_count": 99,
                    "next_page_token": "more",
                }
            }
        ],
        identity_pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,255}$",
        known_identities={"org/model-alpha": "SRC-MODEL-EXISTING"},
    )
    assert model["coverage"]["duplicate_identical_representation_count"] >= 1
    assert model["coverage"]["reported_total_reconciliation_state"] == "PARTIAL_TRAVERSAL_NOT_RECONCILED"
    assert model["coverage"]["missing_optional_state_counts"]["checkpoint"] >= 1

    grants = project_universe_pages(
        universe_id="SU-GRANTS",
        query_id="Q-G",
        query_text="grants",
        pages=[
            {
                "payload": {
                    "items": [{"identity": "GRANT-1", "title": "G1"}],
                    "total_count": 1,
                }
            }
        ],
        identity_pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]{2,127}$",
    )
    assert grants["coverage"]["prohibited_inference"] == "investor_or_funder_to_control"
    assert grants["coverage"]["reported_total_reconciliation_state"] == "MATCH"

    inconsistent = project_universe_pages(
        universe_id="SU-REG",
        query_id="Q-R",
        query_text="reg",
        pages=[
            {
                "payload": {
                    "records": [{"identity": "K123456", "title": "D1"}],
                    "total_count": 1,
                    "next_page_token": "p2",
                }
            },
            {
                "payload": {
                    "records": [{"identity": "K654321", "title": "D2"}],
                    "total_count": 9,
                }
            },
        ],
        identity_pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$",
    )
    assert inconsistent["coverage"]["reported_total_count_state"] == "INCONSISTENT_ACROSS_PAGES"
    assert inconsistent["coverage"]["reported_total_reconciliation_state"] == "DENOMINATOR_UNAVAILABLE"

    mismatch = project_universe_pages(
        universe_id="SU-PUBS",
        query_id="Q",
        query_text="q",
        pages=[
            {
                "payload": {
                    "records": [{"identity": "10.1000/only", "title": "Only"}],
                    "total_count": 5,
                }
            }
        ],
        identity_pattern=pattern,
    )
    assert mismatch["coverage"]["reported_total_reconciliation_state"] == "MISMATCH"

    invalid_identity = project_universe_pages(
        universe_id="SU-PUBS",
        query_id="Q",
        query_text="q",
        pages=[{"payload": {"records": [{"identity": "not-a-doi", "title": "x"}]}}],
        identity_pattern=pattern,
    )
    assert any(item["failure_class"] == "INVALID_IDENTITY" for item in invalid_identity["coverage"]["failures"])


def test_clinicaltrials_projection_edge_cases() -> None:
    adapter = ClinicalTrialsGovAdapter.__new__(ClinicalTrialsGovAdapter)
    with pytest.raises(ValueError, match="query_id"):
        project_search_pages(adapter, query_id=" ", query_text="q", pages=[{}])
    with pytest.raises(ValueError, match="At least one"):
        project_search_pages(adapter, query_id="Q", query_text="q", pages=[])
    with pytest.raises(ValueError, match="invalid NCT"):
        project_search_pages(
            adapter,
            query_id="Q",
            query_text="q",
            pages=[{"payload": {"studies": []}}],
            known_nct_sources={"BAD": "SRC-1"},
        )
    with pytest.raises(ValueError, match="Conflicting controlled"):
        project_search_pages(
            adapter,
            query_id="Q",
            query_text="q",
            pages=[{"payload": {"studies": [_study("NCT00000001", "A")]}}],
            known_nct_sources={"NCT00000001": "SRC-A", "nct00000001": "SRC-B"},
        )
    with pytest.raises(ValueError, match="page must be an object"):
        project_search_pages(adapter, query_id="Q", query_text="q", pages=["x"])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="total_count"):
        project_search_pages(
            adapter,
            query_id="Q",
            query_text="q",
            pages=[{"payload": {"studies": [_study("NCT00000002", "A")], "totalCount": -1}}],
        )
    with pytest.raises(ValueError, match="every study must be an object"):
        project_search_pages(
            adapter,
            query_id="Q",
            query_text="q",
            pages=[{"payload": {"studies": ["not-an-object"]}}],
        )

    class _BadTokenAdapter:
        def parse_search_page(self, payload: dict) -> dict:
            return {"studies": payload.get("studies") or [], "next_page_token": " ", "total_count": None}

        def normalize_study(self, study_payload: dict) -> dict:
            return adapter.normalize_study(study_payload)

    with pytest.raises(ValueError, match="next_page_token"):
        project_search_pages(
            _BadTokenAdapter(),
            query_id="Q",
            query_text="q",
            pages=[{"payload": {"studies": [_study("NCT00000003", "A")]}}],
        )
    with pytest.raises(ValueError, match="pagination sequence"):
        project_search_pages(
            adapter,
            query_id="Q",
            query_text="q",
            pages=[
                {"payload": {"studies": [_study("NCT00000004", "A")], "totalCount": 2}},
                {"payload": {"studies": [_study("NCT00000005", "B")], "totalCount": 2}},
            ],
        )

    partial = project_search_pages(
        adapter,
        query_id="Q",
        query_text="q",
        pages=[
            {
                "payload": {
                    "studies": [_study("NCT00000010", "A")],
                    "totalCount": 2,
                    "nextPageToken": "more",
                }
            }
        ],
        known_nct_sources={"NCT00000010": "SRC-KNOWN"},
    )
    assert partial["coverage"]["reported_total_reconciliation_state"] == "PARTIAL_TRAVERSAL_NOT_RECONCILED"
    assert partial["result_records"][0]["classification_hint"] == "DUPLICATE"

    inconsistent = project_search_pages(
        adapter,
        query_id="Q",
        query_text="q",
        pages=[
            {
                "payload": {
                    "studies": [_study("NCT00000011", "A")],
                    "totalCount": 1,
                    "nextPageToken": "p2",
                }
            },
            {"payload": {"studies": [_study("NCT00000012", "B")], "totalCount": 9}},
        ],
    )
    assert inconsistent["coverage"]["reported_total_count_state"] == "INCONSISTENT_ACROSS_PAGES"

    no_total = project_search_pages(
        adapter,
        query_id="Q",
        query_text="q",
        pages=[{"payload": {"studies": [_study("NCT00000013", "A")]}}],
    )
    assert no_total["coverage"]["reported_total_count_state"] == "NOT_REPORTED"
    assert no_total["coverage"]["reported_total_reconciliation_state"] == "DENOMINATOR_UNAVAILABLE"

    mismatch = project_search_pages(
        adapter,
        query_id="Q",
        query_text="q",
        pages=[{"payload": {"studies": [_study("NCT00000014", "A")], "totalCount": 5}}],
    )
    assert mismatch["coverage"]["reported_total_reconciliation_state"] == "MISMATCH"

    duplicate_identical = project_search_pages(
        adapter,
        query_id="Q",
        query_text="q",
        pages=[
            {
                "payload": {
                    "studies": [
                        _study("NCT00000015", "Same"),
                        _study("NCT00000015", "Same"),
                    ],
                    "totalCount": 1,
                }
            }
        ],
    )
    assert duplicate_identical["coverage"]["duplicate_nct_representation_count"] >= 1

    trial = load_su_trial_programme()
    result = run_source_universe(
        programme=trial,
        execution_mode="OFFLINE_REPLAY",
        pages=[{"payload": {"studies": [_study("NCT00000020", "Anchor")]}}],
    )
    assert result["coverage"]["recall_anchor_nct"] == "NCT03333954"
    assert result["coverage"]["s2_mutated"] is False
