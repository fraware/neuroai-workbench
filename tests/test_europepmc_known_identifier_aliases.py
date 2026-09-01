from __future__ import annotations

import unittest

from neuroai_workbench.discovery.europepmc import project_search_pages


def _page() -> dict:
    return {
        "payload": {
            "hitCount": 1,
            "resultList": {
                "result": [
                    {
                        "source": "MED",
                        "id": "41124203",
                        "pmid": "41124203",
                        "doi": "10.1056/NEJMoa2501396",
                        "title": "Subretinal Photovoltaic Implant to Restore Vision",
                        "authorString": "Example A",
                        "journalTitle": "New England Journal of Medicine",
                        "pubYear": "2025",
                        "pubType": "Journal Article",
                    }
                ]
            },
        }
    }


class EuropePmcKnownIdentifierAliasTests(unittest.TestCase):
    def test_pmid_controlled_identity_matches_doi_resolved_result(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-EPMC-VISUAL-NEUROPROSTHESIS-COMPUTATION-001",
            query_text="TITLE_ABS:(retinal)",
            pages=[_page()],
            known_publication_sources={"PMID:41124203": "SRC-PR-013"},
        )
        record = result["result_records"][0]
        self.assertEqual(record["record_key"], "DOI:10.1056/nejmoa2501396")
        self.assertEqual(record["classification_hint"], "DUPLICATE")
        self.assertEqual(record["duplicate_of_source_id"], "SRC-PR-013")

    def test_conflicting_exact_identifier_aliases_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "conflicting controlled Sources"):
            project_search_pages(
                query_id="DISCOVERY-EPMC-VISUAL-NEUROPROSTHESIS-COMPUTATION-001",
                query_text="TITLE_ABS:(retinal)",
                pages=[_page()],
                known_publication_sources={
                    "DOI:10.1056/nejmoa2501396": "SRC-PR-001",
                    "PMID:41124203": "SRC-PR-013",
                },
            )


if __name__ == "__main__":
    unittest.main()
