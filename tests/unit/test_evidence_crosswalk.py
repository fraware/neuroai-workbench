from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.evidence_crosswalk import (
    build_evidence_crosswalk,
    build_source_universe,
    render_crosswalk_markdown,
    write_crosswalk_outputs,
)


def _sources() -> dict[str, Any]:
    return {
        "metadata": {"version": "current-test"},
        "sources": [
            {"source_id": "SRC-1", "title": "Explicit", "url": "https://example.org/explicit"},
            {"source_id": "SRC-2", "title": "URL", "url": "https://example.org/url/"},
            {"source_id": "SRC-3", "title": "Hash", "url": "https://example.org/hash", "sha256": "HASH-3"},
            {"source_id": "SRC-4", "title": "Both", "url": "https://example.org/both", "checksum": "HASH-4"},
            {"source_id": "SRC-5", "title": "Ambiguous A", "url": "https://example.org/duplicate"},
            {"source_id": "SRC-6", "title": "Ambiguous B", "url": "https://example.org/duplicate/"},
            {"source_id": "SRC-7", "title": "Conflict URL", "url": "https://example.org/conflict"},
            {"source_id": "SRC-8", "title": "Conflict hash", "url": "https://example.org/other", "sha256": "CONFLICT"},
        ],
        "delta": {
            "new_sources": [
                {"source_id": "SRC-9", "title": "Delta source", "url": "https://example.org/delta"},
            ],
            "model_records": [{"model_id": "M1", "source_ids": ["SRC-1", "SRC-2"]}],
        },
    }


def _assessment() -> dict[str, Any]:
    evidence = [
        {
            "evidence_id": "EV-EXPLICIT",
            "title": "Explicit source",
            "source_ids": ["SRC-1"],
            "url_or_path": "https://example.org/explicit",
        },
        {"evidence_id": "EV-URL", "title": "Unique URL", "url_or_path": "https://example.org/url"},
        {"evidence_id": "EV-HASH", "title": "Unique hash", "url_or_path": "/local/hash", "checksum": "hash-3"},
        {
            "evidence_id": "EV-BOTH",
            "title": "URL and hash",
            "url_or_path": "https://example.org/both/",
            "checksum": "hash-4",
        },
        {
            "evidence_id": "EV-AMBIG",
            "title": "Ambiguous URL",
            "url_or_path": "https://example.org/duplicate",
        },
        {
            "evidence_id": "EV-CONFLICT",
            "title": "Conflicting keys",
            "url_or_path": "https://example.org/conflict",
            "checksum": "conflict",
        },
        {
            "evidence_id": "EV-MISSING-ID",
            "title": "Missing explicit ID",
            "source_ids": ["SRC-MISSING"],
        },
        {
            "evidence_id": "EV-UNRESOLVED",
            "title": "Public evidence outside source universe",
            "url_or_path": "https://outside.example/paper",
        },
        {
            "evidence_id": "EV-LOCAL",
            "title": "Unhashed local note",
            "url_or_path": "/controlled/note.txt",
        },
    ]
    findings = [
        {
            "requirement_id": "NK-01-R01",
            "module_id": "NK-01",
            "priority": "P0",
            "finding_status": "PASS",
            "evidence_ids": ["EV-EXPLICIT", "EV-URL"],
        },
        {
            "requirement_id": "NK-01-R02",
            "module_id": "NK-01",
            "priority": "P1",
            "finding_status": "PARTIAL",
            "evidence_ids": ["EV-HASH", "EV-BOTH"],
        },
        {
            "requirement_id": "NK-02-R01",
            "module_id": "NK-02",
            "priority": "P0",
            "finding_status": "NOT_ASSESSED",
            "evidence_ids": ["EV-UNRESOLVED"],
        },
    ]
    return {
        "assessment_metadata": {"assessment_id": "ASSESSMENT-1", "title": "Assessment 1"},
        "system_profile": {"system_name": "System 1"},
        "evidence_register": evidence,
        "requirement_findings": findings,
    }


def _second_assessment() -> dict[str, Any]:
    return {
        "assessment_metadata": {"assessment_id": "ASSESSMENT-2", "title": "Assessment 2"},
        "system_profile": {"system_name": "System 2"},
        "evidence_register": [
            {"evidence_id": "EV-DELTA", "title": "Delta exact", "url_or_path": "https://example.org/delta"},
        ],
        "requirement_findings": [
            {
                "requirement_id": "NK-03-R01",
                "module_id": "NK-03",
                "priority": "P0",
                "finding_status": "PASS",
                "evidence_ids": ["EV-DELTA"],
            }
        ],
    }


def test_source_universe_recurses_only_explicit_source_records() -> None:
    universe = build_source_universe([_sources()])
    assert len(universe) == 9
    assert {row["source_id"] for row in universe} == {f"SRC-{index}" for index in range(1, 10)}
    assert all(row["source_id"] != "M1" for row in universe)


def test_source_universe_merges_sparse_duplicates_and_rejects_conflicts() -> None:
    universe = build_source_universe(
        [
            [{"source_id": "SRC-X", "title": "Sparse"}],
            [{"source_id": "SRC-X", "url": "https://example.org/x", "source_class": "OFFICIAL_PAGE"}],
        ]
    )
    assert universe == [
        {
            "source_id": "SRC-X",
            "title": "Sparse",
            "publisher": None,
            "source_class": "OFFICIAL_PAGE",
            "normalized_public_url": "https://example.org/x",
            "checksum": None,
        }
    ]
    with pytest.raises(ValueError, match="Conflicting normalized_public_url"):
        build_source_universe(
            [
                [{"source_id": "SRC-X", "url": "https://example.org/x"}],
                [{"source_id": "SRC-X", "url": "https://example.org/y"}],
            ]
        )


def test_source_universe_rejects_invalid_or_empty_payloads() -> None:
    with pytest.raises(ValueError, match="At least one"):
        build_source_universe([])
    with pytest.raises(ValueError, match="payload 0"):
        build_source_universe(["bad"])
    with pytest.raises(ValueError, match="contain no source_id"):
        build_source_universe([{"metadata": {"version": "empty"}}])


def test_crosswalk_covers_all_exact_and_unresolved_states() -> None:
    crosswalk = build_evidence_crosswalk([_sources()], [_assessment(), _second_assessment()])
    by_id = {(row["assessment_id"], row["evidence_id"]): row for row in crosswalk["crosswalk"]}

    assert by_id[("ASSESSMENT-1", "EV-EXPLICIT")]["crosswalk_state"] == "EXPLICIT_SOURCE_ID"
    assert by_id[("ASSESSMENT-1", "EV-EXPLICIT")]["candidate_source_ids"] == ["SRC-1"]
    assert by_id[("ASSESSMENT-1", "EV-URL")]["crosswalk_state"] == "EXACT_URL"
    assert by_id[("ASSESSMENT-1", "EV-URL")]["candidate_source_ids"] == ["SRC-2"]
    assert by_id[("ASSESSMENT-1", "EV-HASH")]["crosswalk_state"] == "EXACT_CHECKSUM"
    assert by_id[("ASSESSMENT-1", "EV-HASH")]["candidate_source_ids"] == ["SRC-3"]
    assert by_id[("ASSESSMENT-1", "EV-BOTH")]["crosswalk_state"] == "EXACT_URL_AND_CHECKSUM"
    assert by_id[("ASSESSMENT-1", "EV-BOTH")]["candidate_source_ids"] == ["SRC-4"]
    assert by_id[("ASSESSMENT-1", "EV-AMBIG")]["crosswalk_state"] == "AMBIGUOUS_EXACT"
    assert by_id[("ASSESSMENT-1", "EV-AMBIG")]["candidate_source_ids"] == ["SRC-5", "SRC-6"]
    assert by_id[("ASSESSMENT-1", "EV-CONFLICT")]["crosswalk_state"] == "AMBIGUOUS_EXACT"
    assert by_id[("ASSESSMENT-1", "EV-CONFLICT")]["candidate_source_ids"] == ["SRC-7", "SRC-8"]
    assert by_id[("ASSESSMENT-1", "EV-MISSING-ID")]["crosswalk_state"] == "UNRESOLVED"
    assert by_id[("ASSESSMENT-1", "EV-MISSING-ID")]["missing_explicit_source_ids"] == ["SRC-MISSING"]
    assert by_id[("ASSESSMENT-1", "EV-UNRESOLVED")]["crosswalk_state"] == "UNRESOLVED"
    assert by_id[("ASSESSMENT-1", "EV-UNRESOLVED")]["source_registration_candidate"] is True
    assert by_id[("ASSESSMENT-1", "EV-LOCAL")]["source_registration_candidate"] is False
    assert by_id[("ASSESSMENT-2", "EV-DELTA")]["candidate_source_ids"] == ["SRC-9"]


def test_safe_migration_requires_nonshared_unique_exact_candidate() -> None:
    crosswalk = build_evidence_crosswalk([_sources()], [_assessment()])
    by_id = {row["evidence_id"]: row for row in crosswalk["crosswalk"]}
    assert by_id["EV-EXPLICIT"]["safe_migration_candidate"] is False
    assert by_id["EV-URL"]["safe_migration_candidate"] is True
    assert by_id["EV-HASH"]["safe_migration_candidate"] is True
    assert by_id["EV-BOTH"]["safe_migration_candidate"] is True
    assert by_id["EV-AMBIG"]["safe_migration_candidate"] is False
    assert by_id["EV-UNRESOLVED"]["safe_migration_candidate"] is False


def test_explicit_id_conflict_fails_closed_as_ambiguous() -> None:
    assessment = _assessment()
    assessment["evidence_register"] = [
        {
            "evidence_id": "EV-CONFLICTING-EXPLICIT",
            "title": "Conflicting explicit ID and URL",
            "source_ids": ["SRC-1"],
            "url_or_path": "https://example.org/url",
        }
    ]
    assessment["requirement_findings"] = [{"requirement_id": "NK-X", "evidence_ids": ["EV-CONFLICTING-EXPLICIT"]}]
    row = build_evidence_crosswalk([_sources()], [assessment])["crosswalk"][0]
    assert row["crosswalk_state"] == "AMBIGUOUS_EXACT"
    assert row["candidate_source_ids"] == ["SRC-1", "SRC-2"]
    assert row["match_rule"] == "EXPLICIT_ID_CONFLICT"


def test_url_and_hash_can_disambiguate_duplicate_url() -> None:
    sources = _sources()
    for source in sources["sources"]:
        if source["source_id"] == "SRC-5":
            source["checksum"] = "SPECIAL"
    assessment = _assessment()
    assessment["evidence_register"] = [
        {
            "evidence_id": "EV-DISAMBIG",
            "title": "Disambiguated exact evidence",
            "url_or_path": "https://example.org/duplicate",
            "checksum": "special",
        }
    ]
    assessment["requirement_findings"] = [{"requirement_id": "NK-X", "evidence_ids": ["EV-DISAMBIG"]}]
    row = build_evidence_crosswalk([sources], [assessment])["crosswalk"][0]
    assert row["crosswalk_state"] == "EXACT_URL_AND_CHECKSUM"
    assert row["candidate_source_ids"] == ["SRC-5"]


def test_summary_and_requirement_rollup_are_explicit() -> None:
    crosswalk = build_evidence_crosswalk([_sources()], [_assessment(), _second_assessment()])
    summary = crosswalk["summary"]
    assert crosswalk["metadata"] == {
        "title": "NeuroAI deterministic assessment-evidence crosswalk",
        "source_count": 9,
        "assessment_count": 2,
        "evidence_count": 10,
        "fuzzy_matching": False,
    }
    assert summary["matched_evidence_count"] == 5
    assert summary["ambiguous_evidence_count"] == 2
    assert summary["unresolved_evidence_count"] == 3
    assert summary["safe_migration_candidate_count"] == 4
    assert summary["source_registration_candidate_count"] == 1
    assert summary["missing_explicit_source_reference_count"] == 1
    assert summary["matched_requirement_ids"] == ["NK-01-R01", "NK-01-R02", "NK-03-R01"]

    by_assessment = {row["assessment_id"]: row for row in crosswalk["by_assessment"]}
    assert by_assessment["ASSESSMENT-1"]["matched_evidence_count"] == 4
    assert by_assessment["ASSESSMENT-1"]["matched_requirement_count"] == 2
    assert by_assessment["ASSESSMENT-1"]["requirement_count"] == 3
    assert by_assessment["ASSESSMENT-2"]["matched_evidence_count"] == 1
    assert by_assessment["ASSESSMENT-2"]["matched_requirement_count"] == 1


def test_source_diagnostics_surface_duplicate_exact_keys() -> None:
    crosswalk = build_evidence_crosswalk([_sources()], [_assessment()])
    duplicates = crosswalk["source_diagnostics"]["duplicate_normalized_urls"]
    assert duplicates == [
        {
            "normalized_public_url": "https://example.org/duplicate",
            "source_ids": ["SRC-5", "SRC-6"],
            "count": 2,
        }
    ]
    assert crosswalk["source_diagnostics"]["duplicate_checksums"] == []


def test_outputs_are_machine_readable_and_human_inspectable(tmp_path: Path) -> None:
    crosswalk = build_evidence_crosswalk([_sources()], [_assessment(), _second_assessment()])
    markdown = render_crosswalk_markdown(crosswalk)
    assert "# NeuroAI evidence crosswalk" in markdown
    assert "Safe migration candidates: 4" in markdown
    assert "SRC-MISSING" in markdown

    outputs = write_crosswalk_outputs(crosswalk, tmp_path / "crosswalk")
    for value in outputs.values():
        assert Path(value).is_file()
    payload = json.loads(Path(outputs["json"]).read_text(encoding="utf-8"))
    assert payload["metadata"]["evidence_count"] == 10
    with Path(outputs["csv"]).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 10
    explicit = next(row for row in rows if row["evidence_id"] == "EV-EXPLICIT")
    assert explicit["candidate_source_ids"] == "SRC-1"
    assert Path(outputs["markdown"]).read_text(encoding="utf-8") == markdown
