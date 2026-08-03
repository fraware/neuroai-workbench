from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.discovery import (
    DISCOVERY_BOUNDARY,
    EXPECTED_FIXTURE_QUERY_IDS,
    DiscoveryError,
    DiscoveryNetworkBlockedError,
    DiscoveryOverwriteRefusedError,
    adjudicate_candidate_source,
    execute_discovery_query,
    get_fixture_query,
    list_fixture_queries,
    load_run,
    load_successor,
    network_discovery_allowed,
    refuse_registry_overwrite,
    require_accepted_proposals_for_successor,
    seed_fixture_queries,
)
from neuroai_workbench.discovery.schemas import (
    ADJUDICATION_SCHEMA,
    PROPOSAL_SCHEMA,
    QUERY_SCHEMA,
    RUN_SCHEMA,
    SUCCESSOR_SCHEMA,
    schema_errors,
)


def test_fixture_query_ids_match_audit_examples() -> None:
    queries = list_fixture_queries()
    ids = [item["query_id"] for item in queries]
    assert ids == list(EXPECTED_FIXTURE_QUERY_IDS)
    assert all(not schema_errors(item, QUERY_SCHEMA) for item in queries)
    assert all("do not authorize registry mutation" in item["boundary"] for item in queries)
    assert "candidate source proposals" in DISCOVERY_BOUNDARY.lower()


def test_offline_execution_classifies_new_duplicate_excluded(tmp_path: Path) -> None:
    seed_fixture_queries(tmp_path)
    known = [{"source_id": "SRC-KNOWN-001", "url": "https://example.org/known-source"}]
    result = execute_discovery_query(
        tmp_path,
        "DISCOVERY-CLINICAL-TRIALS-BCI",
        actor="reviewer-a",
        known_sources=known,
    )
    run = result["run"]
    assert run["execution_mode"] == "OFFLINE_FIXTURE"
    assert run["result_counts"] == {"total": 3, "new": 1, "duplicate": 1, "excluded": 1}
    assert run["automatic_registry_mutation_performed"] is False
    assert not schema_errors(run, RUN_SCHEMA)

    by_class = {p["classification"]: p for p in result["proposals"]}
    assert by_class["NEW"]["status"] == "PENDING_HUMAN_ACCEPTANCE"
    assert by_class["DUPLICATE"]["duplicate_of_source_id"] == "SRC-KNOWN-001"
    assert by_class["EXCLUDED"]["status"] == "EXCLUDED"
    assert all(not schema_errors(p, PROPOSAL_SCHEMA) for p in result["proposals"])


def test_human_accept_creates_append_only_successor(tmp_path: Path) -> None:
    seed_fixture_queries(tmp_path)
    result = execute_discovery_query(tmp_path, "DISCOVERY-CLINICAL-TRIALS-BCI")
    new_proposal = next(p for p in result["proposals"] if p["classification"] == "NEW")

    outcome = adjudicate_candidate_source(
        tmp_path,
        new_proposal["proposal_id"],
        "ACCEPT",
        rationale="Public synthetic source accepted for successor draft only.",
        actor="reviewer-b",
        base_registry_version="v-test-base",
        proposed_registry_version="v-test-successor",
    )
    assert outcome["proposal"]["status"] == "ACCEPTED"
    assert outcome["adjudication"]["identity_boundary"] == "LOCAL_UNAUTHENTICATED_ATTRIBUTION"
    assert outcome["adjudication"]["automatic_mutation_performed"] is False
    assert not schema_errors(outcome["adjudication"], ADJUDICATION_SCHEMA)

    successor = outcome["successor"]
    assert successor is not None
    assert successor["overwrite_refused"] is True
    assert successor["status"] == "DRAFT_SUCCESSOR"
    assert successor["proposed_registry_version"] == "v-test-successor"
    assert not schema_errors(successor, SUCCESSOR_SCHEMA)
    loaded = load_successor(tmp_path, successor["successor_id"])
    assert loaded["accepted_proposal_ids"] == [new_proposal["proposal_id"]]

    run = load_run(tmp_path, result["run"]["run_id"])
    assert run["adjudication_status"] == "PARTIALLY_ADJUDICATED"


def test_reject_and_defer_do_not_create_successor(tmp_path: Path) -> None:
    seed_fixture_queries(tmp_path)
    result = execute_discovery_query(tmp_path, "DISCOVERY-CLINICAL-TRIALS-BCI")
    duplicate = next(p for p in result["proposals"] if p["classification"] == "DUPLICATE")
    outcome = adjudicate_candidate_source(
        tmp_path,
        duplicate["proposal_id"],
        "REJECT",
        rationale="Already present in baseline registry.",
        actor="reviewer-c",
    )
    assert outcome["successor"] is None
    assert outcome["proposal"]["status"] == "REJECTED"


def test_opt_in_network_blocked_without_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEUROAI_LIVE_DISCOVERY", raising=False)
    assert network_discovery_allowed() is False
    seed_fixture_queries(tmp_path)
    with pytest.raises(DiscoveryNetworkBlockedError, match="NEUROAI_LIVE_DISCOVERY=1"):
        execute_discovery_query(
            tmp_path,
            "DISCOVERY-PUBMED-NEUROAI",
            execution_mode="OPT_IN_NETWORK",
            result_records=[
                {
                    "record_key": "PM-1",
                    "title": "Synthetic",
                    "url": "https://example.org/pm/1",
                    "publisher": "PubMed Fixture",
                    "source_class": "PEER_REVIEWED",
                    "suggested_source_id": "SRC-PM-1",
                }
            ],
        )


def test_opt_in_network_with_gate_validates_urls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEUROAI_LIVE_DISCOVERY", "1")
    seed_fixture_queries(tmp_path)
    result = execute_discovery_query(
        tmp_path,
        "DISCOVERY-FDA-NEURAL-INTERFACE",
        execution_mode="OPT_IN_NETWORK",
        result_records=[
            {
                "record_key": "FDA-SYNTH-1",
                "title": "Synthetic neural interface listing",
                "url": "https://example.org/fda/SYNTH-1",
                "publisher": "FDA Fixture",
                "source_class": "REGULATORY_RECORD",
                "suggested_source_id": "SRC-FDA-SYNTH-1",
                "classification_hint": "NEW",
            }
        ],
        actor="ops-user",
    )
    assert result["run"]["execution_mode"] == "OPT_IN_NETWORK"
    assert result["run"]["network_gate"]["allowed"] is True
    assert result["run"]["result_counts"]["new"] == 1


def test_refuse_registry_overwrite() -> None:
    with pytest.raises(DiscoveryOverwriteRefusedError, match="never silently overwrites"):
        refuse_registry_overwrite(target_path="registry.json")


def test_successor_requires_accepted_proposal(tmp_path: Path) -> None:
    seed_fixture_queries(tmp_path)
    result = execute_discovery_query(tmp_path, "DISCOVERY-CLINICAL-TRIALS-BCI")
    pending = next(p for p in result["proposals"] if p["status"] == "PENDING_HUMAN_ACCEPTANCE")
    with pytest.raises(Exception, match="human ACCEPT required"):
        require_accepted_proposals_for_successor([pending["proposal_id"]], tmp_path)


def test_cannot_accept_duplicate_into_successor(tmp_path: Path) -> None:
    seed_fixture_queries(tmp_path)
    result = execute_discovery_query(tmp_path, "DISCOVERY-CLINICAL-TRIALS-BCI")
    duplicate = next(p for p in result["proposals"] if p["classification"] == "DUPLICATE")
    with pytest.raises(DiscoveryError, match="Only NEW"):
        adjudicate_candidate_source(
            tmp_path,
            duplicate["proposal_id"],
            "ACCEPT",
            rationale="Should fail",
        )


def test_get_fixture_query_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown fixture"):
        get_fixture_query("DISCOVERY-NOT-A-REAL-QUERY")
