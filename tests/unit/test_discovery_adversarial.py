from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.discovery import (
    DiscoveryNetworkBlockedError,
    adjudicate_candidate_source,
    execute_discovery_query,
    load_proposal,
    seed_fixture_queries,
    validate_discovery_url,
)
from neuroai_workbench.discovery.store import _proposals_dir
from neuroai_workbench.util import safe_join


def test_ssrf_blocks_private_discovery_urls() -> None:
    with pytest.raises(DiscoveryNetworkBlockedError, match="SSRF"):
        validate_discovery_url("http://127.0.0.1/internal")
    with pytest.raises(DiscoveryNetworkBlockedError, match="SSRF"):
        validate_discovery_url("http://169.254.169.254/latest/meta-data")
    with pytest.raises(DiscoveryNetworkBlockedError, match="SSRF"):
        validate_discovery_url("http://localhost/admin")


def test_opt_in_network_rejects_ssrf_result_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEUROAI_LIVE_DISCOVERY", "1")
    seed_fixture_queries(tmp_path)
    with pytest.raises(DiscoveryNetworkBlockedError, match="SSRF"):
        execute_discovery_query(
            tmp_path,
            "DISCOVERY-GRANTS-NEURAL-DECODING",
            execution_mode="OPT_IN_NETWORK",
            result_records=[
                {
                    "record_key": "BAD-1",
                    "title": "Internal grant mirror",
                    "url": "http://10.0.0.5/grants",
                    "publisher": "Internal",
                    "source_class": "GRANT",
                    "suggested_source_id": "SRC-BAD-1",
                }
            ],
        )


def test_proposal_path_rejects_escape(tmp_path: Path) -> None:
    seed_fixture_queries(tmp_path)
    root = _proposals_dir(tmp_path)
    root.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="Path escapes controlled root"):
        safe_join(root, "..", "secrets.json")


def test_load_proposal_rejects_invalid_identifier(tmp_path: Path) -> None:
    seed_fixture_queries(tmp_path)
    with pytest.raises(ValueError, match="Invalid proposal_id"):
        load_proposal(tmp_path, "../escape")


def test_accept_with_private_url_blocked(tmp_path: Path) -> None:
    seed_fixture_queries(tmp_path)
    result = execute_discovery_query(
        tmp_path,
        "DISCOVERY-DATASETS-EEG-FOUNDATION-MODEL",
        result_records=[
            {
                "record_key": "DS-1",
                "title": "Synthetic EEG corpus listing",
                "url": "https://example.org/datasets/eeg-1",
                "publisher": "Catalog Fixture",
                "source_class": "DATASET_CATALOG",
                "suggested_source_id": "SRC-DS-1",
                "classification_hint": "NEW",
            }
        ],
    )
    proposal = result["proposals"][0]
    # Tamper stored proposal URL to a private target before acceptance.
    from neuroai_workbench.discovery.store import store_proposal

    poisoned = {
        **proposal,
        "proposed_source": {
            **proposal["proposed_source"],
            "url": "http://192.168.1.10/datasets",
        },
    }
    store_proposal(tmp_path, poisoned)
    with pytest.raises(DiscoveryNetworkBlockedError, match="SSRF"):
        adjudicate_candidate_source(
            tmp_path,
            proposal["proposal_id"],
            "ACCEPT",
            rationale="Must fail closed on private URL",
        )
