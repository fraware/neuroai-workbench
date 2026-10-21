"""Synthetic regression checks for the frozen review-table extraction path."""

from __future__ import annotations

import hashlib

import pytest

from scripts.r1_7_extract_review_device_tables import (
    FORM_FACTORS,
    PMCID,
    PMID,
    RAW_SOURCE_SHA256,
    extract_table_rows,
)


def _synthetic(*, count: int = 6, header: str = "Device") -> bytes:
    tables = []
    for number in range(1, count + 1):
        cells = "".join(f"<th>{name}</th>" for name in [header, "A", "B", "C", "D", "E", "F"])
        row = "".join(f"<td>{value}</td>" for value in [f"Mock-{number}", "1", "2", "3", "4", "5", "6"])
        tables.append(
            f"<table-wrap><label>Table {number}</label><caption><title>Synthetic {number}</title></caption>"
            f"<table><thead><tr>{cells}</tr></thead><tbody><tr>{row}</tr></tbody></table></table-wrap>"
        )
    return (
        f'<article><front><article-meta><article-id pub-id-type="pmid">{PMID}</article-id>'
        f'<article-id pub-id-type="pmcid">{PMCID}</article-id>'
        "</article-meta></front><body>" + "".join(tables) + "</body></article>"
    ).encode()


def test_synthetic_extraction_retains_cell_and_table_provenance() -> None:
    raw = _synthetic()
    report = extract_table_rows(raw, frozen_source=False)
    assert len(FORM_FACTORS) == 6
    assert report["raw_row_count"] == 6
    assert report["source_evidence_sha256"] == hashlib.sha256(raw).hexdigest()
    assert len({row["raw_device_designation"] for row in report["rows"]}) == 6
    assert [row["table_number"] for row in report["rows"]] == list(range(1, 7))
    assert all(row["canonical_offering_id"] is None for row in report["rows"])
    assert all(row["commercial_availability"] == "NOT_ASSESSED" for row in report["rows"])
    assert all(row["candidate_status"] == "UNRESOLVED_TABLE_ROW_MENTION" for row in report["rows"])
    assert all(len(row["raw_row_content_sha256"]) == 64 for row in report["rows"])


def test_frozen_source_is_digest_bound() -> None:
    assert len(RAW_SOURCE_SHA256) == 64
    with pytest.raises(ValueError, match="exact acquired source"):
        extract_table_rows(_synthetic())


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (_synthetic(count=5), "Expected six"),
        (_synthetic(header="Offering"), "nonconforming seven-column"),
        (b"<html>Not an article</html>", "JATS article"),
    ],
)
def test_invalid_table_source_fails_closed(source: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        extract_table_rows(source, frozen_source=False)
