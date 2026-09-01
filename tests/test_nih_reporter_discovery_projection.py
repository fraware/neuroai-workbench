from __future__ import annotations

import unittest

from neuroai_workbench.discovery.nih_reporter import project_search_pages


def _record(appl_id: int, *, project_num: str, core: str = "R01NS000001", title: str = "Neural interface grant") -> dict:
    return {
        "appl_id": appl_id,
        "subproject_id": None,
        "fiscal_year": 2026,
        "project_num": project_num,
        "core_project_num": core,
        "project_title": title,
        "abstract_text": "Machine learning for neural decoding.",
        "project_start_date": "2026-01-01",
        "project_end_date": "2030-12-31",
        "award_notice_date": "2026-07-01",
        "award_amount": 500000,
        "funding_mechanism": "Research Projects",
        "agency_ic_admin": {"code": "NINDS"},
        "organization": {"org_name": "Example University", "org_country": "UNITED STATES"},
        "principal_investigators": [{"full_name": "Example Investigator"}],
    }


def _page(rows: list[dict], *, total: int, offset: int = 0, limit: int = 500) -> dict:
    return {"payload": {"meta": {"total": total, "offset": offset, "limit": limit}, "results": rows}}


class NihReporterDiscoveryProjectionTests(unittest.TestCase):
    def test_projects_exact_application_identity_and_metadata(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-REPORTER-BCI-001",
            query_payload={"criteria": {"advanced_text_search": {"operator": "or", "search_field": "projecttitle,abstracttext,terms", "search_text": "BCI"}}},
            pages=[_page([_record(12345678, project_num="1R01NS000001-01")], total=1)],
        )
        self.assertEqual(result["result_records"][0]["record_key"], "REPORTER:APPL:12345678")
        normalized = result["normalized_records"][0]
        self.assertEqual(normalized["appl_id"], 12345678)
        self.assertEqual(normalized["project_num"], "1R01NS000001-01")
        self.assertEqual(normalized["core_project_num"], "R01NS000001")
        self.assertEqual(normalized["award_amount"], 500000)
        self.assertEqual(result["coverage"]["offset_coverage_state"], "MATCH")
        self.assertFalse(result["coverage"]["funding_success_claim"])
        self.assertFalse(result["coverage"]["automatic_pi_or_org_entity_creation_performed"])

    def test_exact_known_appl_id_marks_duplicate(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-REPORTER-BCI-001",
            query_payload={"criteria": {"advanced_text_search": {"operator": "or", "search_field": "all", "search_text": "BCI"}}},
            pages=[_page([_record(123, project_num="1R01NS000001-01")], total=1)],
            known_appl_sources={123: "SRC-GRANT-001"},
        )
        self.assertEqual(result["result_records"][0]["classification_hint"], "DUPLICATE")
        self.assertEqual(result["result_records"][0]["duplicate_of_source_id"], "SRC-GRANT-001")
        self.assertEqual(result["coverage"]["new_candidate_count"], 0)

    def test_support_year_applications_do_not_auto_merge(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-REPORTER-BCI-001",
            query_payload={"criteria": {"advanced_text_search": {"operator": "or", "search_field": "all", "search_text": "BCI"}}},
            pages=[_page([
                _record(1001, project_num="1R01NS000001-01"),
                _record(1002, project_num="5R01NS000001-02"),
            ], total=2)],
        )
        self.assertEqual({row["record_key"] for row in result["result_records"]}, {"REPORTER:APPL:1001", "REPORTER:APPL:1002"})

    def test_over_15000_refuses_candidate_emission(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-REPORTER-GREY-MENTAL-STATE-001",
            query_payload={"criteria": {"advanced_text_search": {"operator": "or", "search_field": "all", "search_text": "EEG"}}},
            pages=[_page([_record(1001, project_num="1R01NS000001-01")], total=15001)],
        )
        self.assertTrue(result["coverage"]["over_15000_limit"])
        self.assertTrue(result["coverage"]["partition_required"])
        self.assertTrue(result["coverage"]["candidate_emission_refused_due_to_over_limit"])
        self.assertEqual(result["result_records"], [])
        self.assertEqual(result["normalized_records"], [])

    def test_noncontiguous_offsets_are_visible(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-REPORTER-BCI-001",
            query_payload={"criteria": {"advanced_text_search": {"operator": "or", "search_field": "all", "search_text": "BCI"}}},
            pages=[
                _page([_record(1, project_num="P1")], total=2, offset=0, limit=1),
                _page([_record(2, project_num="P2")], total=2, offset=2, limit=1),
            ],
        )
        self.assertFalse(result["coverage"]["offset_sequence_valid"])
        self.assertEqual(result["coverage"]["offset_coverage_state"], "INVALID_SEQUENCE")

    def test_conflicting_same_appl_id_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Conflicting normalized RePORTER representations"):
            project_search_pages(
                query_id="DISCOVERY-REPORTER-BCI-001",
                query_payload={"criteria": {"advanced_text_search": {"operator": "or", "search_field": "all", "search_text": "BCI"}}},
                pages=[
                    _page([_record(1, project_num="P1", title="Title A")], total=1, offset=0, limit=1),
                    _page([_record(1, project_num="P1", title="Title B")], total=1, offset=1, limit=1),
                ],
            )

    def test_normalized_digest_is_query_independent(self) -> None:
        page = _page([_record(42, project_num="1R01NS000001-01")], total=1)
        a = project_search_pages(query_id="DISCOVERY-REPORTER-BCI-001", query_payload={"q": "a"}, pages=[page])
        b = project_search_pages(query_id="DISCOVERY-REPORTER-NEURAL-DECODING-AI-001", query_payload={"q": "b"}, pages=[page])
        self.assertNotEqual(a["normalized_records"][0]["query_memberships"], b["normalized_records"][0]["query_memberships"])
        self.assertEqual(a["normalized_records"][0]["normalized_record_sha256"], b["normalized_records"][0]["normalized_record_sha256"])


if __name__ == "__main__":
    unittest.main()
