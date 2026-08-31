from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlparse

from neuroai_workbench.collector.adapters.clinicaltrials import ClinicalTrialsGovAdapter


class ClinicalTrialsSearchRequestOptionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = ClinicalTrialsGovAdapter.__new__(ClinicalTrialsGovAdapter)

    def test_count_total_is_explicit_opt_in(self) -> None:
        without_total = parse_qs(urlparse(self.adapter.build_search_url("BCI", page_size=100)).query)
        with_total = parse_qs(
            urlparse(self.adapter.build_search_url("BCI", page_size=100, count_total=True)).query
        )
        self.assertNotIn("countTotal", without_total)
        self.assertEqual(with_total["countTotal"], ["true"])
        self.assertEqual(with_total["query.term"], ["BCI"])
        self.assertEqual(with_total["pageSize"], ["100"])

    def test_source_record_can_request_total_count(self) -> None:
        self.assertTrue(self.adapter.extract_count_total({"count_total": True}))
        self.assertTrue(self.adapter.extract_count_total({"metadata": {"countTotal": "true"}}))
        self.assertFalse(self.adapter.extract_count_total({"metadata": {"countTotal": "false"}}))
        self.assertFalse(self.adapter.extract_count_total(None))


if __name__ == "__main__":
    unittest.main()
