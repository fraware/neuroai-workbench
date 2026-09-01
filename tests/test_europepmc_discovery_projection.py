from __future__ import annotations

import unittest

from neuroai_workbench.discovery.europepmc import project_search_pages


def _record(
    *,
    source: str = "MED",
    ext_id: str,
    title: str,
    doi: str | None = None,
    pmid: str | None = None,
    pmcid: str | None = None,
    pub_type: str | list[str] | None = "Journal Article",
) -> dict:
    row = {
        "id": ext_id,
        "source": source,
        "title": title,
        "authorString": "Example A, Example B",
        "journalTitle": "Example Journal" if source != "PPR" else "bioRxiv",
        "pubYear": "2026",
    }
    if doi is not None:
        row["doi"] = doi
    if pmid is not None:
        row["pmid"] = pmid
    if pmcid is not None:
        row["pmcid"] = pmcid
    if pub_type is not None:
        row["pubType"] = pub_type
    return row


def _page(rows: list[dict], *, hit_count: int | None = None, next_cursor: str | None = None) -> dict:
    payload: dict = {"resultList": {"result": rows}}
    if hit_count is not None:
        payload["hitCount"] = hit_count
    if next_cursor is not None:
        payload["nextCursorMark"] = next_cursor
    return {"payload": payload}


class EuropePmcDiscoveryProjectionTests(unittest.TestCase):
    def test_projects_terminal_query_with_exact_identifier_precedence(self) -> None:
        pages = [
            _page(
                [
                    _record(
                        ext_id="41124203",
                        title="PRIMA",
                        doi="https://doi.org/10.1056/NEJMoa2501396",
                        pmid="41124203",
                        pmcid="PMC7618305",
                    ),
                    _record(
                        ext_id="39141853",
                        title="Speech neuroprosthesis",
                        doi="10.1056/NEJMoa2314132",
                        pmid="39141853",
                        pmcid="PMC11328962",
                    ),
                ],
                hit_count=2,
            )
        ]
        result = project_search_pages(
            query_id="DISCOVERY-EPMC-SPEECH-COMMUNICATION-001",
            query_text='TITLE_ABS:(speech AND neuroprosthesis)',
            pages=pages,
        )
        self.assertEqual(
            [row["record_key"] for row in result["result_records"]],
            ["DOI:10.1056/nejmoa2314132", "DOI:10.1056/nejmoa2501396"],
        )
        self.assertEqual(result["coverage"]["reported_hit_count_state"], "CONSISTENT")
        self.assertEqual(result["coverage"]["reported_total_reconciliation_state"], "MATCH")
        self.assertEqual(result["coverage"]["terminal_cursor_state"], "TERMINAL")
        self.assertFalse(result["coverage"]["publication_database_completeness_claim"])
        self.assertFalse(result["coverage"]["query_recall_claim"])
        self.assertFalse(result["coverage"]["global_neuroai_publication_recall_claim"])
        self.assertFalse(result["coverage"]["automatic_source_admission_performed"])
        self.assertFalse(result["coverage"]["automatic_relationship_creation_performed"])
        self.assertFalse(result["coverage"]["automatic_assessment_mutation_performed"])

    def test_exact_known_identity_marks_duplicate_without_url_matching(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-EPMC-VISUAL-001",
            query_text="PRIMA",
            pages=[
                _page(
                    [
                        _record(
                            ext_id="41124203",
                            title="PRIMA",
                            doi="10.1056/NEJMoa2501396",
                            pmid="41124203",
                        )
                    ],
                    hit_count=1,
                )
            ],
            known_publication_sources={"DOI:10.1056/nejmoa2501396": "SRC-PRIMA-PAPER"},
        )
        record = result["result_records"][0]
        self.assertEqual(record["classification_hint"], "DUPLICATE")
        self.assertEqual(record["duplicate_of_source_id"], "SRC-PRIMA-PAPER")
        self.assertEqual(result["coverage"]["known_controlled_source_duplicate_count"], 1)
        self.assertEqual(result["coverage"]["new_candidate_count"], 0)

    def test_pmid_then_pmcid_then_source_ext_id_fallbacks(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-EPMC-ID-FALLBACK",
            query_text="test",
            pages=[
                _page(
                    [
                        _record(ext_id="12345678", title="PMID", pmid="12345678", doi=None),
                        _record(source="PMC", ext_id="PMC999", title="PMCID", pmcid="PMC999", doi=None),
                        _record(source="AGR", ext_id="AGR-1", title="Fallback", doi=None, pmid=None, pmcid=None),
                    ],
                    hit_count=3,
                )
            ],
        )
        self.assertEqual(
            {row["record_key"] for row in result["result_records"]},
            {"PMID:12345678", "PMCID:PMC999", "EPMC:AGR:AGR-1"},
        )

    def test_preprint_source_is_preserved_not_auto_merged(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-EPMC-PREPRINT",
            query_text="foundation model",
            pages=[
                _page(
                    [
                        _record(
                            source="PPR",
                            ext_id="PPR123",
                            title="Preprint",
                            doi="10.1101/2026.01.01.123456",
                            pub_type="preprint",
                        )
                    ],
                    hit_count=1,
                )
            ],
        )
        normalized = result["normalized_records"][0]
        self.assertTrue(normalized["is_preprint"])
        self.assertEqual(normalized["source"], "PPR")
        self.assertEqual(result["coverage"]["preprint_count"], 1)
        self.assertEqual(result["coverage"]["peer_reviewed_or_journal_count"], 0)

    def test_identical_duplicate_across_pages_collapses(self) -> None:
        record = _record(
            ext_id="39141853",
            title="Speech neuroprosthesis",
            doi="10.1056/NEJMoa2314132",
            pmid="39141853",
        )
        result = project_search_pages(
            query_id="DISCOVERY-EPMC-DUP",
            query_text="speech",
            pages=[
                _page([record], hit_count=1, next_cursor="cursor-2"),
                _page([record], hit_count=1),
            ],
        )
        self.assertEqual(len(result["result_records"]), 1)
        self.assertEqual(result["coverage"]["cross_query_duplicate_representation_count"], 1)
        self.assertEqual(result["coverage"]["reported_total_reconciliation_state"], "MATCH")

    def test_conflicting_same_identity_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Conflicting normalized Europe PMC representations"):
            project_search_pages(
                query_id="DISCOVERY-EPMC-CONFLICT",
                query_text="speech",
                pages=[
                    _page(
                        [_record(ext_id="1", title="Title A", doi="10.1234/example")],
                        hit_count=1,
                        next_cursor="cursor-2",
                    ),
                    _page(
                        [_record(ext_id="1", title="Title B", doi="10.1234/example")],
                        hit_count=1,
                    ),
                ],
            )

    def test_nonfinal_page_without_cursor_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-final page 1 has no nextCursorMark"):
            project_search_pages(
                query_id="DISCOVERY-EPMC-PAGINATION",
                query_text="BCI",
                pages=[
                    _page([_record(ext_id="1", title="A", doi="10.1234/a")]),
                    _page([_record(ext_id="2", title="B", doi="10.1234/b")]),
                ],
            )

    def test_partial_traversal_does_not_reconcile_denominator(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-EPMC-PARTIAL",
            query_text="BCI",
            pages=[
                _page(
                    [_record(ext_id="1", title="A", doi="10.1234/a")],
                    hit_count=2,
                    next_cursor="more",
                )
            ],
        )
        self.assertEqual(result["coverage"]["terminal_cursor_state"], "NONTERMINAL")
        self.assertEqual(
            result["coverage"]["reported_total_reconciliation_state"],
            "PARTIAL_TRAVERSAL_NOT_RECONCILED",
        )

    def test_terminal_denominator_mismatch_is_visible(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-EPMC-MISMATCH",
            query_text="BCI",
            pages=[
                _page(
                    [_record(ext_id="1", title="A", doi="10.1234/a")],
                    hit_count=2,
                )
            ],
        )
        self.assertEqual(result["coverage"]["terminal_cursor_state"], "TERMINAL")
        self.assertEqual(result["coverage"]["reported_total_reconciliation_state"], "MISMATCH")

    def test_inconsistent_hit_count_is_reported_not_repaired(self) -> None:
        result = project_search_pages(
            query_id="DISCOVERY-EPMC-HITCOUNT",
            query_text="BCI",
            pages=[
                _page(
                    [_record(ext_id="1", title="A", doi="10.1234/a")],
                    hit_count=2,
                    next_cursor="c2",
                ),
                _page(
                    [_record(ext_id="2", title="B", doi="10.1234/b")],
                    hit_count=3,
                ),
            ],
        )
        self.assertEqual(result["coverage"]["reported_hit_count_state"], "INCONSISTENT_ACROSS_PAGES")
        self.assertIsNone(result["coverage"]["reported_hit_count"])
        self.assertEqual(result["coverage"]["reported_hit_count_values"], [2, 3])
        self.assertEqual(result["coverage"]["reported_total_reconciliation_state"], "DENOMINATOR_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
