from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from neuroai_workbench.discovery.errors import DiscoveryError
from neuroai_workbench.discovery.workflow import execute_discovery_query


class DiscoveryOfflineReplayTests(unittest.TestCase):
    def test_recorded_public_results_are_not_labeled_fixture_or_network(self) -> None:
        records = [
            {
                "record_key": "NCT04676854",
                "title": "PRIMAvera replay candidate",
                "url": "https://clinicaltrials.gov/study/NCT04676854",
                "publisher": "ClinicalTrials.gov",
                "source_class": "OFFICIAL_TRIAL_REGISTRY",
                "suggested_source_id": "SRC-CTGOV-NCT04676854",
                "classification_hint": "DUPLICATE",
                "duplicate_of_source_id": "SRC-PR-002",
            }
        ]
        with tempfile.TemporaryDirectory() as td:
            outcome = execute_discovery_query(
                Path(td),
                "DISCOVERY-CLINICAL-TRIALS-BCI",
                execution_mode="OFFLINE_REPLAY",
                result_records=records,
                executed_at="2026-08-31T00:00:00Z",
            )

        self.assertEqual(outcome["run"]["execution_mode"], "OFFLINE_REPLAY")
        self.assertIsNone(outcome["run"]["network_gate"])
        self.assertEqual(outcome["run"]["result_counts"], {"total": 1, "new": 0, "duplicate": 1, "excluded": 0})
        self.assertEqual(outcome["proposals"][0]["status"], "PENDING_HUMAN_ACCEPTANCE")
        self.assertEqual(outcome["proposals"][0]["duplicate_of_source_id"], "SRC-PR-002")
        self.assertFalse(outcome["run"]["automatic_registry_mutation_performed"])

    def test_replay_requires_explicit_records(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(DiscoveryError, "OFFLINE_REPLAY execution requires"):
                execute_discovery_query(
                    Path(td),
                    "DISCOVERY-CLINICAL-TRIALS-BCI",
                    execution_mode="OFFLINE_REPLAY",
                    executed_at="2026-08-31T00:00:00Z",
                )


if __name__ == "__main__":
    unittest.main()
