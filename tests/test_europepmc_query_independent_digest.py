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
                        "id": "39141853",
                        "pmid": "39141853",
                        "doi": "10.1056/NEJMoa2314132",
                        "title": "An Accurate and Rapidly Calibrating Speech Neuroprosthesis",
                        "authorString": "Example A",
                        "journalTitle": "New England Journal of Medicine",
                        "pubYear": "2024",
                        "pubType": "Journal Article",
                    }
                ]
            },
        }
    }


class EuropePmcQueryIndependentDigestTests(unittest.TestCase):
    def test_same_publication_has_same_content_digest_across_query_memberships(self) -> None:
        first = project_search_pages(
            query_id="DISCOVERY-EPMC-BCI-001",
            query_text="TITLE_ABS:(BCI)",
            pages=[_page()],
        )["normalized_records"][0]
        second = project_search_pages(
            query_id="DISCOVERY-EPMC-SPEECH-COMMUNICATION-001",
            query_text="TITLE_ABS:(speech)",
            pages=[_page()],
        )["normalized_records"][0]

        self.assertNotEqual(first["query_memberships"], second["query_memberships"])
        self.assertEqual(first["normalized_record_sha256"], second["normalized_record_sha256"])
        first_without_membership = {k: v for k, v in first.items() if k != "query_memberships"}
        second_without_membership = {k: v for k, v in second.items() if k != "query_memberships"}
        self.assertEqual(first_without_membership, second_without_membership)


if __name__ == "__main__":
    unittest.main()
