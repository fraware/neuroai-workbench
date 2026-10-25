"""Deterministic boundary tests for PubMed bare numeric URL identifiers."""

from __future__ import annotations

import pytest

from neuroai_workbench.collector.adapters.pubmed import PubmedCrossrefAdapter


@pytest.fixture
def adapter() -> PubmedCrossrefAdapter:
    # Only exercise the pure identifier-extraction method; no HTTP requests.
    return object.__new__(PubmedCrossrefAdapter)


def test_real_pubmed_https_numeric_path_is_admitted(adapter: PubmedCrossrefAdapter) -> None:
    for url in (
        "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        "https://pubmed.ncbi.nlm.nih.gov/12345678",
        "https://pubmed.ncbi.nlm.nih.gov/12345678/?format=pubmed",
        "https://pubmed.ncbi.nlm.nih.gov:443/12345678/",
        "https://PUBMED.NCBI.NLM.NIH.GOV/12345678/",
    ):
        assert adapter.extract_publication_id(None, {"requested_url": url}) == ("PMID", "12345678")


@pytest.mark.parametrize(
    "url",
    (
        "https://pubmed.ncbi.nlm.nih.gov.example.org/12345678/",
        "https://example.org/redirect/pubmed.ncbi.nlm.nih.gov/12345678/",
        "http://pubmed.ncbi.nlm.nih.gov/12345678/",
        "https://pubmed.ncbi.nlm.nih.gov/some-path/12345678/",
        "https://pubmed.ncbi.nlm.nih.gov/?term=12345678",
        "https://user@pubmed.ncbi.nlm.nih.gov/12345678/",
        "https://user:secret@pubmed.ncbi.nlm.nih.gov/12345678/",
        "https://@pubmed.ncbi.nlm.nih.gov/12345678/",
        "https://pubmed.ncbi.nlm.nih.gov:444/12345678/",
        "https://pubmed.ncbi.nlm.nih.gov:80/12345678/",
        "https://pubmed.ncbi.nlm.nih.gov:0/12345678/",
        "https://pubmed.ncbi.nlm.nih.gov:invalid/12345678/",
        "https://pubmed.ncbi.nlm.nih.gov:65536/12345678/",
    ),
)
def test_unapproved_source_url_cannot_infer_bare_pmid(adapter: PubmedCrossrefAdapter, url: str) -> None:
    assert adapter.extract_publication_id(None, {"requested_url": url}) is None


@pytest.mark.parametrize(
    "url",
    (
        "https://[invalid/12345678/",
        "https://[::1/12345678/",
    ),
)
def test_malformed_urls_fail_closed_without_raising(adapter: PubmedCrossrefAdapter, url: str) -> None:
    assert adapter.extract_publication_id(None, {"requested_url": url}) is None


def test_explicit_pmid_in_trusted_metadata_preserved(adapter: PubmedCrossrefAdapter) -> None:
    assert adapter.extract_publication_id(
        {"pmid": "12345678"}, {"requested_url": "https://example.org/not-a-pubmed-id"}
    ) == ("PMID", "12345678")
