from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from neuroai_workbench.collector.adapters.clinicaltrials import ClinicalTrialsGovAdapter
from neuroai_workbench.discovery.clinicaltrials import project_search_pages
from neuroai_workbench.discovery.workflow import execute_discovery_query


def _study(nct_id: str, title: str, status: str = "RECRUITING") -> dict:
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct_id, "briefTitle": title},
            "statusModule": {
                "overallStatus": status,
                "lastUpdatePostDateStruct": {"date": "2026-08-01"},
                "primaryCompletionDateStruct": {"date": "2027-01"},
                "enrollmentInfo": {"count": 20},
            },
            "designModule": {"phases": ["NA"]},
        }
    }


class ClinicalTrialsDiscoveryProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        # parse_search_page/normalize_study are pure with respect to adapter instance state;
        # bypass HttpCollector construction so these tests remain offline.
        self.adapter = ClinicalTrialsGovAdapter.__new__(ClinicalTrialsGovAdapter)

    def test_projects_bounded_query_traversal(self) -> None:
        pages = [
            {"payload": {"studies": [_study("NCT00000001", "First BCI trial")], "totalCount": 2, "nextPageToken": "p2"}},
            {"payload": {"studies": [_study("NCT00000002", "Second BCI trial")], "totalCount": 2}},
        ]
        result = project_search_pages(
            self.adapter,
            query_id="DISCOVERY-CLINICAL-TRIALS-BCI",
            query_text="brain-computer interface",
            pages=pages,
        )
        self.assertEqual([row["record_key"] for row in result["result_records"]], ["NCT00000001", "NCT00000002"])
        self.assertEqual(result["coverage"]["reported_total_count_state"], "CONSISTENT")
        self.assertEqual(result["coverage"]["reported_total_count"], 2)
        self.assertTrue(result["coverage"]["fully_paginated"])
        self.assertFalse(result["coverage"]["registry_completeness_claim"])
        self.assertFalse(result["coverage"]["neuroai_discovery_recall_claim"])
        self.assertFalse(result["coverage"]["automatic_registry_mutation_performed"])

    def test_identical_duplicate_across_pages_deduplicates(self) -> None:
        study = _study("NCT00000003", "Repeated result")
        result = project_search_pages(
            self.adapter,
            query_id="DISCOVERY-CLINICAL-TRIALS-BCI",
            query_text="BCI",
            pages=[
                {"payload": {"studies": [study], "totalCount": 1, "nextPageToken": "next"}},
                {"payload": {"studies": [study], "totalCount": 1}},
            ],
        )
        self.assertEqual(len(result["result_records"]), 1)
        self.assertEqual(result["coverage"]["duplicate_nct_representation_count"], 1)

    def test_conflicting_same_nct_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Conflicting normalized"):
            project_search_pages(
                self.adapter,
                query_id="DISCOVERY-CLINICAL-TRIALS-BCI",
                query_text="BCI",
                pages=[
                    {"payload": {"studies": [_study("NCT00000004", "Title A")], "nextPageToken": "next"}},
                    {"payload": {"studies": [_study("NCT00000004", "Title B")]}},
                ],
            )

    def test_inconsistent_total_count_is_reported_not_repaired(self) -> None:
        result = project_search_pages(
            self.adapter,
            query_id="DISCOVERY-CLINICAL-TRIALS-BCI",
            query_text="BCI",
            pages=[
                {"payload": {"studies": [_study("NCT00000005", "A")], "totalCount": 2, "nextPageToken": "next"}},
                {"payload": {"studies": [_study("NCT00000006", "B")], "totalCount": 3}},
            ],
        )
        self.assertEqual(result["coverage"]["reported_total_count_state"], "INCONSISTENT_ACROSS_PAGES")
        self.assertIsNone(result["coverage"]["reported_total_count"])
        self.assertEqual(result["coverage"]["reported_total_count_values"], [2, 3])

    def test_results_feed_generic_discovery_without_automatic_mutation(self) -> None:
        projection = project_search_pages(
            self.adapter,
            query_id="DISCOVERY-CLINICAL-TRIALS-BCI",
            query_text="brain-computer interface",
            pages=[{"payload": {"studies": [_study("NCT00000007", "Candidate trial")]}}],
        )
        with tempfile.TemporaryDirectory() as td:
            outcome = execute_discovery_query(
                Path(td),
                "DISCOVERY-CLINICAL-TRIALS-BCI",
                execution_mode="OFFLINE_FIXTURE",
                result_records=projection["result_records"],
                executed_at="2026-08-31T00:00:00Z",
            )
        self.assertEqual(outcome["run"]["result_counts"], {"total": 1, "new": 1, "duplicate": 0, "excluded": 0})
        self.assertEqual(outcome["proposals"][0]["status"], "PENDING_HUMAN_ACCEPTANCE")
        self.assertFalse(outcome["run"]["automatic_registry_mutation_performed"])
        self.assertFalse(outcome["proposals"][0]["automatic_mutation_performed"])


if __name__ == "__main__":
    unittest.main()
