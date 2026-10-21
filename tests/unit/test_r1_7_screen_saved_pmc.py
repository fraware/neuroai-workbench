"""Offline tests for literal, nonterminal screening of saved JATS article bodies."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.r1_7_screen_saved_pmc import screen_saved_article, main


def _article(pmid: str, body: str) -> bytes:
    return (
        f'<article><front><article-meta><article-id pub-id-type="pmid">{pmid}</article-id>'
        '</article-meta></front><body><sec><title>Methods</title>'
        f'<p>{body}</p></sec></body><back><ref-list><ref><mixed-citation>'
        'Emotiv Insight in bibliography only</mixed-citation></ref></ref-list></back></article>'
    ).encode("utf-8")


def test_literal_mentions_are_source_bound_and_nonterminal(tmp_path: Path) -> None:
    saved = tmp_path / "pmid-42505450-fulltext.xml"
    saved.write_bytes(_article("42505450", "We discuss OpenBCI Galea and Muse systems."))
    result = screen_saved_article(saved)
    assert result["status"] == "CANDIDATE_MENTION_SCREENING_ONLY"
    assert result["product_identity_or_completion_inferred"] is False
    assert result["mention_count"] == 2
    assert [entry["term"] for entry in result["mentions"]] == ["OpenBCI Galea", "Muse"]
    assert all(entry["disposition"] == "UNRESOLVED_MENTION_FOR_REVIEW" for entry in result["mentions"])
    assert not any(entry["term"] == "Emotiv Insight" for entry in result["mentions"])
    assert all(len(entry["passage_sha256"]) == 64 for entry in result["mentions"])


def test_screening_rejects_wrong_pmid_and_non_articles(tmp_path: Path) -> None:
    wrong = tmp_path / "pmid-42505450-fulltext.xml"
    wrong.write_bytes(_article("99999999", "Muse"))
    with pytest.raises(ValueError, match="PMID differs"):
        screen_saved_article(wrong)
    wrong.write_bytes(b"<html><body>Muse</body></html>")
    with pytest.raises(ValueError, match="JATS article"):
        screen_saved_article(wrong)


def test_cli_reads_saved_bytes_only(tmp_path: Path) -> None:
    source = tmp_path / "raw"
    source.mkdir()
    (source / "pmid-41939223-fulltext.xml").write_bytes(_article("41939223", "A Bitbrain headset was studied."))
    output = tmp_path / "screening.json"
    assert main(["--input-dir", str(source), "--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "NONTERMINAL_SCREENING_ONLY"
    assert report["papers"][0]["mention_count"] == 1
    assert report["papers"][0]["mentions"][0]["term"] == "Bitbrain"


def test_cli_fails_when_no_saved_source_exists(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="2"):
        main(["--input-dir", str(tmp_path), "--output", str(tmp_path / "screening.json")])
