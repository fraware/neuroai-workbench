from __future__ import annotations

import unittest

from neuroai_workbench.discovery.epo_ops import project_search_pages


def _xml(
    records: list[tuple[str, str, str, str]],
    *,
    total: int,
    begin: int = 1,
    end: int | None = None,
) -> str:
    if end is None:
        end = max(begin, begin + len(records) - 1)
    docs = []
    for country, number, kind, title in records:
        docs.append(
            f"""
            <exchange-document country="{country}" doc-number="{number}" kind="{kind}">
              <bibliographic-data>
                <publication-reference>
                  <document-id document-id-type="docdb">
                    <country>{country}</country><doc-number>{number}</doc-number><kind>{kind}</kind><date>20260801</date>
                  </document-id>
                </publication-reference>
                <application-reference>
                  <document-id document-id-type="docdb"><country>{country}</country><doc-number>APP{number}</doc-number><kind>A</kind></document-id>
                </application-reference>
                <priority-claims>
                  <priority-claim><document-id><country>US</country><doc-number>PR{number}</doc-number><date>20250101</date></document-id></priority-claim>
                </priority-claims>
                <parties>
                  <applicants><applicant><applicant-name><name>Example Applicant</name></applicant-name></applicant></applicants>
                  <inventors><inventor><inventor-name><name>Example Inventor</name></inventor-name></inventor></inventors>
                </parties>
                <invention-title lang="en">{title}</invention-title>
                <classification-ipcr><text>A61B 5/00</text></classification-ipcr>
              </bibliographic-data>
              <abstract lang="en"><p>Example neural-interface abstract.</p></abstract>
            </exchange-document>
            """
        )
    return f"""
    <world-patent-data>
      <biblio-search total-result-count="{total}">
        <query syntax="CQL">ta=neural</query>
        <range begin="{begin}" end="{end}" />
        <search-result>{''.join(docs)}</search-result>
      </biblio-search>
    </world-patent-data>
    """


class EpoOpsDiscoveryProjectionTests(unittest.TestCase):
    def test_projects_exact_docdb_identity_and_bibliographic_fields(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-OPS-BCI-001",
            query_text='ta all "brain computer interface"',
            pages=[{"xml": _xml([("EP", "1234567", "A1", "Neural interface")], total=1)}],
        )
        self.assertEqual(result["result_records"][0]["record_key"], "DOCDB:EP:1234567:A1")
        normalized = result["normalized_records"][0]
        self.assertEqual(normalized["title"], "Neural interface")
        self.assertEqual(normalized["applicants"], ["Example Applicant"])
        self.assertEqual(normalized["inventors"], ["Example Inventor"])
        self.assertEqual(normalized["publication_date"], "20260801")
        self.assertEqual(result["coverage"]["reported_total_result_count_state"], "CONSISTENT")
        self.assertEqual(result["coverage"]["range_coverage_state"], "MATCH")
        self.assertFalse(result["coverage"]["partition_required"])
        self.assertFalse(result["coverage"]["automatic_family_creation_performed"])
        self.assertFalse(result["coverage"]["automatic_entity_creation_performed"])
        self.assertFalse(result["coverage"]["automatic_product_or_system_relationship_creation_performed"])

    def test_exact_known_docdb_marks_duplicate(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-OPS-BCI-001",
            query_text="ta=neural",
            pages=[{"xml": _xml([("WO", "2026123456", "A1", "BCI")], total=1)}],
            known_docdb_sources={"DOCDB:WO:2026123456:A1": "SRC-PAT-001"},
        )
        self.assertEqual(result["result_records"][0]["classification_hint"], "DUPLICATE")
        self.assertEqual(result["result_records"][0]["duplicate_of_source_id"], "SRC-PAT-001")
        self.assertEqual(result["coverage"]["known_controlled_duplicate_count"], 1)
        self.assertEqual(result["coverage"]["new_candidate_count"], 0)

    def test_publication_steps_do_not_auto_merge(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-OPS-BCI-001",
            query_text="ta=neural",
            pages=[{
                "xml": _xml(
                    [("EP", "1234567", "A1", "Application"), ("EP", "1234567", "B1", "Grant")],
                    total=2,
                )
            }],
        )
        self.assertEqual(
            {row["record_key"] for row in result["result_records"]},
            {"DOCDB:EP:1234567:A1", "DOCDB:EP:1234567:B1"},
        )
        self.assertFalse(result["coverage"]["patent_family_completeness_claim"])

    def test_over_2000_refuses_candidate_emission_and_requires_partition(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-OPS-GREY-MENTAL-STATE-001",
            query_text="ta=EEG",
            pages=[{"xml": _xml([("EP", "1", "A1", "One")], total=2001, end=100)}],
        )
        self.assertTrue(result["coverage"]["over_2000_limit"])
        self.assertTrue(result["coverage"]["partition_required"])
        self.assertTrue(result["coverage"]["candidate_emission_refused_due_to_over_limit"])
        self.assertEqual(result["coverage"]["range_coverage_state"], "OVER_LIMIT_PARTITION_REQUIRED")
        self.assertEqual(result["result_records"], [])
        self.assertEqual(result["normalized_records"], [])

    def test_noncontiguous_ranges_are_visible(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-OPS-BCI-001",
            query_text="ta=neural",
            pages=[
                {"xml": _xml([("EP", "1", "A1", "One")], total=2, begin=1, end=1)},
                {"xml": _xml([("EP", "2", "A1", "Two")], total=2, begin=3, end=3)},
            ],
        )
        self.assertFalse(result["coverage"]["range_sequence_valid"])
        self.assertEqual(result["coverage"]["range_coverage_state"], "INVALID_SEQUENCE")

    def test_conflicting_same_docdb_identity_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Conflicting normalized OPS representations"):
            project_search_pages(
                query_id="DISCOVERY-OPS-BCI-001",
                query_text="ta=neural",
                pages=[
                    {"xml": _xml([("EP", "123", "A1", "Title A")], total=1, begin=1, end=1)},
                    {"xml": _xml([("EP", "123", "A1", "Title B")], total=1, begin=2, end=2)},
                ],
            )

    def test_normalized_digest_is_query_membership_independent(self) -> None:
        page = {"xml": _xml([("EP", "7654321", "A1", "Neural decoder")], total=1)}
        first = project_search_pages(query_id="DISCOVERY-OPS-BCI-001", query_text="ta=neural", pages=[page])
        second = project_search_pages(query_id="DISCOVERY-OPS-NEURAL-DECODING-AI-001", query_text="ta=decoder", pages=[page])
        self.assertNotEqual(first["normalized_records"][0]["query_memberships"], second["normalized_records"][0]["query_memberships"])
        self.assertEqual(
            first["normalized_records"][0]["normalized_record_sha256"],
            second["normalized_records"][0]["normalized_record_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
