from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from neuroai_workbench.collector.adapters.clinicaltrials import ClinicalTrialsGovAdapter
from neuroai_workbench.discovery.clinicaltrials import project_search_pages
from neuroai_workbench.discovery.workflow import execute_discovery_query


def _study(
    nct_id: str,
    title: str,
    status: str = "RECRUITING",
    study_type: str = "INTERVENTIONAL",
) -> dict:
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct_id, "briefTitle": title},
            "statusModule": {
                "overallStatus": status,
                "lastUpdatePostDateStruct": {"date": "2026-08-01"},
                "primaryCompletionDateStruct": {"date": "2027-01"},
                "enrollmentInfo": {"count": 20},
            },
            "designModule": {"studyType": study_type, "phases": ["NA"]},
        }
    }


class ClinicalTrialsDiscoveryProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = ClinicalTrialsGovAdapter.__new__(ClinicalTrialsGovAdapter)

    def test_projects_bounded_query_traversal(self) -> None:
        pages = [
            {"payload": {"studies": [_study("NCT00000001", "First BCI trial")], "totalCount": 2, "nextPageToken": "p2"}},
            {"payload": {"studies": [_study("NCT00000002", "Second BCI trial")]}},
        ]
        result = project_search_pages(
            self.adapter,
            query_id="DISCOVERY-CLINICAL-TRIALS-BCI",
            query_text="brain-computer interface",
            pages=pages,
            required_study_types=["INTERVENTIONAL"],
        )
        self.assertEqual([row["record_key"] for row in result["result_records"]], ["NCT00000001", "NCT00000002"])
        self.assertEqual(result["coverage"]["reported_total_count_state"], "CONSISTENT")
        self.assertEqual(result["coverage"]["reported_total_count"], 2)
        self.assertEqual(result["coverage"]["reported_total_reconciliation_state"], "MATCH")
        self.assertEqual(result["coverage"]["required_study_types"], ["INTERVENTIONAL"])
        self.assertEqual(result["coverage"]["excluded_by_study_type_count"], 0)
        self.assertTrue(result["coverage"]["pagination_sequence_valid"])
        self.assertTrue(result["coverage"]["fully_paginated"])
        self.assertFalse(result["coverage"]["registry_completeness_claim"])
        self.assertFalse(result["coverage"]["neuroai_discovery_recall_claim"])
        self.assertFalse(result["coverage"]["automatic_registry_mutation_performed"])

    def test_study_type_filter_preserves_denominator_and_exclusion(self) -> None:
        result = project_search_pages(
            self.adapter,
            query_id="DISCOVERY-CLINICAL-TRIALS-BCI",
            query_text="neural interface",
            pages=[{"payload": {"studies": [
                _study("NCT00000008", "Interventional", study_type="INTERVENTIONAL"),
                _study("NCT00000009", "Observational", study_type="OBSERVATIONAL"),
            ], "totalCount": 2}}],
            required_study_types=["INTERVENTIONAL"],
        )
        self.assertEqual(result["coverage"]["unique_nct_record_count_before_programme_filter"], 2)
        self.assertEqual(result["coverage"]["included_candidate_count"], 1)
        self.assertEqual(result["coverage"]["new_candidate_count"], 1)
        self.assertEqual(result["coverage"]["excluded_by_study_type_count"], 1)
        self.assertEqual(result["coverage"]["excluded_by_study_type"][0]["nct_id"], "NCT00000009")
        self.assertEqual(result["result_records"][0]["record_key"], "NCT00000008")

    def test_identical_duplicate_across_pages_deduplicates(self) -> None:
        study = _study("NCT00000003", "Repeated result")
        result = project_search_pages(
            self.adapter,
            query_id="DISCOVERY-CLINICAL-TRIALS-BCI",
            query_text="BCI",
            pages=[
                {"payload": {"studies": [study], "totalCount": 1, "nextPageToken": "next"}},
                {"payload": {"studies": [study]}},
            ],
        )
        self.assertEqual(len(result["result_records"]), 1)
        self.assertEqual(result["coverage"]["duplicate_nct_representation_count"], 1)
        self.assertEqual(result["coverage"]["reported_total_reconciliation_state"], "MATCH")

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

    def test_nonfinal_page_without_cursor_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-final page 1 has no nextPageToken"):
            project_search_pages(
                self.adapter,
                query_id="DISCOVERY-CLINICAL-TRIALS-BCI",
                query_text="BCI",
                pages=[
                    {"payload": {"studies": [_study("NCT00000010", "A")]}},
                    {"payload": {"studies": [_study("NCT00000011", "B")]}},
                ],
            )

    def test_partial_traversal_is_not_denominator_reconciled(self) -> None:
        result = project_search_pages(
            self.adapter,
            query_id="DISCOVERY-CLINICAL-TRIALS-BCI",
            query_text="BCI",
            pages=[{"payload": {"studies": [_study("NCT00000012", "A")], "totalCount": 2, "nextPageToken": "more"}}],
        )
        self.assertFalse(result["coverage"]["fully_paginated"])
        self.assertEqual(result["coverage"]["reported_total_reconciliation_state"], "PARTIAL_TRAVERSAL_NOT_RECONCILED")

    def test_terminal_traversal_count_mismatch_is_visible(self) -> None:
        result = project_search_pages(
            self.adapter,
            query_id="DISCOVERY-CLINICAL-TRIALS-BCI",
            query_text="BCI",
            pages=[{"payload": {"studies": [_study("NCT00000013", "A")], "totalCount": 2}}],
        )
        self.assertTrue(result["coverage"]["fully_paginated"])
        self.assertEqual(result["coverage"]["reported_total_reconciliation_state"], "MISMATCH")

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
        self.assertEqual(result["coverage"]["reported_total_reconciliation_state"], "DENOMINATOR_UNAVAILABLE")

    def test_exact_known_nct_identity_overrides_url_variant(self) -> None:
        projection = project_search_pages(
            self.adapter,
            query_id="DISCOVERY-CLINICAL-TRIALS-BCI",
            query_text="retinal prosthesis",
            pages=[{"payload": {"studies": [_study("NCT04676854", "PRIMAvera")], "totalCount": 1}}],
            required_study_types=["INTERVENTIONAL"],
            known_nct_sources={"NCT04676854": "SRC-PR-002"},
        )
        record = projection["result_records"][0]
        self.assertEqual(record["classification_hint"], "DUPLICATE")
        self.assertEqual(record["duplicate_of_source_id"], "SRC-PR-002")
        self.assertEqual(projection["coverage"]["known_nct_duplicate_count"], 1)
        self.assertEqual(projection["coverage"]["new_candidate_count"], 0)

        with tempfile.TemporaryDirectory() as td:
            outcome = execute_discovery_query(
                Path(td),
                "DISCOVERY-CLINICAL-TRIALS-BCI",
                execution_mode="OFFLINE_FIXTURE",
                result_records=projection["result_records"],
                executed_at="2026-08-31T00:00:00Z",
            )
        self.assertEqual(outcome["run"]["result_counts"], {"total": 1, "new": 0, "duplicate": 1, "excluded": 0})
        self.assertEqual(outcome["proposals"][0]["duplicate_of_source_id"], "SRC-PR-002")
        self.assertEqual(outcome["proposals"][0]["status"], "PENDING_HUMAN_ACCEPTANCE")

    def test_results_feed_generic_discovery_without_automatic_mutation(self) -> None:
        projection = project_search_pages(
            self.adapter,
            query_id="DISCOVERY-CLINICAL-TRIALS-BCI",
            query_text="brain-computer interface",
            pages=[{"payload": {"studies": [_study("NCT00000007", "Candidate trial")]}}],
            required_study_types=["INTERVENTIONAL"],
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
