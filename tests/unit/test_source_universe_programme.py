from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from neuroai_workbench.discovery import (
    SU_TRIAL_DOC_ALIAS,
    SU_TRIAL_ID,
    DiscoveryError,
    DiscoveryService,
    load_su_trial_programme,
    run_source_universe,
    validate_programme,
)
from neuroai_workbench.discovery.store import initialize_discovery_workspace, seed_fixture_queries


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


class SourceUniverseProgrammeTests(unittest.TestCase):
    def test_stable_id_is_su_trial_not_silent_rename(self) -> None:
        programme = load_su_trial_programme()
        self.assertEqual(programme["universe_id"], SU_TRIAL_ID)
        self.assertIn(SU_TRIAL_DOC_ALIAS, programme["documentation_aliases"])
        with self.assertRaises(DiscoveryError):
            validate_programme({**programme, "universe_id": SU_TRIAL_DOC_ALIAS})

    def test_prima_anchor_is_metadata_only(self) -> None:
        programme = load_su_trial_programme()
        anchors = programme["evaluation"]["discovery_recall_anchors"]
        self.assertEqual(anchors[0]["nct_id"], "NCT03333954")
        self.assertEqual(anchors[0]["role"], "EXTERNAL_RECALL_ANCHOR_ONLY")
        source = Path("src/neuroai_workbench/discovery/programme.py").read_text(encoding="utf-8")
        self.assertNotIn(
            "NCT03333954", Path("src/neuroai_workbench/discovery/clinicaltrials.py").read_text(encoding="utf-8")
        )
        self.assertIn("EXTERNAL_RECALL_ANCHOR_ONLY", source)

    def test_programme_emits_candidates_with_coverage_and_exact_nct(self) -> None:
        pages = [
            {"payload": {"studies": [_study("NCT00000001", "First")], "totalCount": 1}},
        ]
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            initialize_discovery_workspace(workspace)
            seed_fixture_queries(workspace)
            result = run_source_universe(
                programme=load_su_trial_programme(),
                execution_mode="OFFLINE_FIXTURE",
                pages=pages,
                workspace=workspace,
                known_nct_sources={"NCT00000001": "SRC-EXISTING"},
            )
        self.assertTrue(result["candidates_only"])
        self.assertFalse(result["coverage"]["s2_mutated"])
        self.assertFalse(result["coverage"]["prima_query_hardcoded"])
        self.assertEqual(result["projection"]["result_records"][0]["classification_hint"], "DUPLICATE")
        self.assertEqual(result["workflow"]["run"]["automatic_registry_mutation_performed"], False)

    def test_url_variant_does_not_create_false_new(self) -> None:
        pages = [{"payload": {"studies": [_study("NCT00000009", "Known")]}}]
        result = run_source_universe(
            programme=load_su_trial_programme(),
            execution_mode="OFFLINE_REPLAY",
            pages=pages,
            known_nct_sources={"NCT00000009": "SRC-KNOWN"},
        )
        record = result["projection"]["result_records"][0]
        self.assertEqual(record["url"], "https://clinicaltrials.gov/study/NCT00000009")
        self.assertEqual(record["classification_hint"], "DUPLICATE")

    def test_conflicting_same_identity_fails_closed(self) -> None:
        pages = [
            {
                "payload": {
                    "studies": [
                        _study("NCT00000003", "One title"),
                        _study("NCT00000003", "Other title"),
                    ]
                }
            }
        ]
        with self.assertRaises(ValueError):
            run_source_universe(programme=load_su_trial_programme(), execution_mode="OFFLINE_REPLAY", pages=pages)

    def test_invalid_mode_missing_pages_and_unknown_universe(self) -> None:
        programme = load_su_trial_programme()
        with self.assertRaises(DiscoveryError):
            run_source_universe(programme=programme, execution_mode="LIVE_SCRAPE", pages=[{"payload": {"studies": []}}])
        with self.assertRaises(DiscoveryError):
            run_source_universe(programme=programme, execution_mode="OFFLINE_REPLAY", pages=None)
        foreign = {**programme, "universe_id": "SU-PUBLICATION"}
        with self.assertRaises(DiscoveryError):
            run_source_universe(
                programme=foreign,
                execution_mode="OFFLINE_REPLAY",
                pages=[{"payload": {"studies": [_study("NCT00000001", "x")]}}],
            )

    def test_authorized_network_mode_still_has_no_http_client(self) -> None:
        from neuroai_workbench.discovery.errors import DiscoveryNetworkBlockedError

        pages = [{"payload": {"studies": [_study("NCT00000011", "Net")]}}]
        with self.assertRaises(DiscoveryNetworkBlockedError):
            run_source_universe(
                programme=load_su_trial_programme(),
                execution_mode="AUTHORIZED_NETWORK",
                pages=pages,
            )

    def test_discovery_service_facade_offline(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            initialize_discovery_workspace(workspace)
            seed_fixture_queries(workspace)
            result = DiscoveryService().run(workspace, "DISCOVERY-CLINICAL-TRIALS-BCI")
            self.assertEqual(result["run"]["execution_mode"], "OFFLINE_FIXTURE")
            self.assertFalse(result["run"]["automatic_registry_mutation_performed"])
