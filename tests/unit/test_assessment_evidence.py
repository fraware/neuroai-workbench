from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.assessment_evidence import (
    build_assessment_evidence_analysis,
    normalize_assessment_evidence,
    normalize_checksum,
    normalize_public_url,
    render_evidence_health_markdown,
    write_assessment_evidence_outputs,
)


def _legacy() -> dict[str, Any]:
    return {
        "assessment_metadata": {
            "assessment_id": "LEGACY-1",
            "title": "Legacy assessment",
            "instrument_version": "4.1.3",
            "evidence_cutoff": "2026-07-28",
        },
        "system_profile": {"system_name": "Legacy System"},
        "evidence_register": [
            {
                "evidence_id": "EV-URL",
                "title": "Public paper",
                "source": "Journal",
                "evidence_class": "PEER_REVIEWED",
                "url_or_path": "HTTPS://Example.org/paper/",
                "published": "2026-06-01",
                "checksum": "NOT CLAIMED — URL evidence",
            },
            {
                "evidence_id": "EV-HASH",
                "title": "Controlled local artifact",
                "source": "Repository",
                "evidence_class": "CODE_SNAPSHOT",
                "url_or_path": "/controlled/code.txt",
                "checksum": "ABC123",
            },
            {
                "evidence_id": "EV-SHARED",
                "title": "Shared source namespace",
                "source_ids": ["SRC-X"],
                "url_or_path": "https://registry.example/study",
            },
            {
                "evidence_id": "EV-LOCAL",
                "title": "Local uncited note",
                "url_or_path": "/controlled/note.txt",
            },
        ],
        "requirement_findings": [
            {
                "requirement_id": "NK-01-R01",
                "module_id": "NK-01",
                "priority": "P0",
                "finding_status": "PASS",
                "evidence_ids": ["EV-URL", "EV-HASH"],
            },
            {
                "requirement_id": "NK-01-R02",
                "module_id": "NK-01",
                "priority": "P1",
                "finding_status": "PARTIAL",
                "evidence_ids": ["EV-URL", "EV-SHARED"],
            },
            {
                "requirement_id": "NK-02-R01",
                "module_id": "NK-02",
                "priority": "P0",
                "finding_status": "NOT ASSESSED",
                "evidence_ids": [],
            },
        ],
    }


def _current() -> dict[str, Any]:
    return {
        "metadata": {
            "assessment_id": "CURRENT-1",
            "title": "Current assessment",
            "instrument_version": "4.2",
            "assessment_version": "4.2.1",
            "evidence_cutoff": "2026-07-30",
        },
        "system": {"system_name": "Current System"},
        "sources": [
            {
                "source_id": "EV-C1",
                "title": "Current shared source",
                "publisher": "Registry",
                "evidence_type": "OFFICIAL_REGISTRY",
                "source_ids": ["SRC-X"],
                "url": "https://registry.example/study/",
                "retrieved": "2026-07-30",
                "evidence_state": "CURRENT_SOURCE_RETRIEVED",
            },
            {
                "source_id": "EV-C2",
                "title": "Same public paper in current assessment",
                "publisher": "Journal",
                "url": "https://example.org/paper",
            },
        ],
        "requirement_findings": [
            {
                "requirement_id": "NK-03-R01",
                "module_id": "NK-03",
                "module": "Current module",
                "priority": "P0",
                "status": "PASS",
                "evidence_ids": ["EV-C1", "EV-C2"],
            },
            {
                "requirement_id": "NK-03-R02",
                "module_id": "NK-03",
                "priority": "P1",
                "status": "PARTIAL",
                "evidence_ids": ["EV-C1"],
            },
        ],
    }


def test_normalization_helpers_keep_namespaces_explicit() -> None:
    assert normalize_public_url("HTTPS://Example.org/path/#fragment") == "https://example.org/path"
    assert normalize_public_url("/controlled/local.txt") is None
    assert normalize_public_url(None) is None
    assert normalize_checksum("ABCDEF") == "abcdef"
    assert normalize_checksum("NOT CLAIMED — URL evidence") is None
    assert normalize_checksum("N/A") is None
    assert normalize_checksum(None) is None


def test_normalize_legacy_evidence_links_and_orphans() -> None:
    package = normalize_assessment_evidence(_legacy())
    assert package["identity"]["assessment_id"] == "LEGACY-1"
    assert len(package["evidence"]) == 4
    assert len(package["findings"]) == 3
    assert len(package["links"]) == 4
    assert package["duplicate_evidence_ids"] == []
    assert package["dangling_evidence_ids"] == []

    by_id = {row["evidence_id"]: row for row in package["evidence"]}
    assert by_id["EV-URL"]["namespace_state"] == "PUBLIC_URL_ONLY"
    assert by_id["EV-URL"]["normalized_public_url"] == "https://example.org/paper"
    assert by_id["EV-URL"]["cited_requirement_count"] == 2
    assert by_id["EV-HASH"]["namespace_state"] == "HASHED_LOCAL"
    assert by_id["EV-HASH"]["checksum"] == "abc123"
    assert by_id["EV-SHARED"]["namespace_state"] == "SHARED_SOURCE_ID"
    assert by_id["EV-SHARED"]["source_ids"] == ["SRC-X"]
    assert by_id["EV-LOCAL"]["namespace_state"] == "ASSESSMENT_LOCAL"
    assert by_id["EV-LOCAL"]["cited_requirement_count"] == 0

    zero = next(row for row in package["findings"] if row["requirement_id"] == "NK-02-R01")
    assert zero["evidence_count"] == 0


def test_normalize_current_shape_preserves_versions_and_dates() -> None:
    package = normalize_assessment_evidence(_current())
    identity = package["identity"]
    assert identity["assessment_version"] == "4.2.1"
    assert identity["system_name"] == "Current System"
    by_id = {row["evidence_id"]: row for row in package["evidence"]}
    assert by_id["EV-C1"]["namespace_state"] == "SHARED_SOURCE_ID"
    assert by_id["EV-C1"]["retrieval_date"] == "2026-07-30"
    assert by_id["EV-C1"]["evidence_state"] == "CURRENT_SOURCE_RETRIEVED"


def test_analysis_surfaces_health_and_cross_assessment_overlaps() -> None:
    analysis = build_assessment_evidence_analysis([_legacy(), _current()])
    metadata = analysis["metadata"]
    health = analysis["health"]
    assert metadata == {
        "title": "NeuroAI assessment evidence analytical projection",
        "assessment_count": 2,
        "evidence_count": 6,
        "finding_count": 5,
        "evidence_requirement_link_count": 7,
        "fuzzy_matching": False,
    }
    assert health["namespace_counts"] == {
        "ASSESSMENT_LOCAL": 1,
        "HASHED_LOCAL": 1,
        "PUBLIC_URL_ONLY": 2,
        "SHARED_SOURCE_ID": 2,
    }
    assert health["orphan_evidence_count"] == 1
    assert health["zero_evidence_requirement_count"] == 1
    assert health["shared_source_id_evidence_count"] == 2
    assert health["public_url_evidence_count"] == 4
    assert health["checksum_evidence_count"] == 1
    assert health["duplicate_evidence_ids"] == []
    assert health["dangling_evidence_links"] == []

    duplicate_urls = health["duplicate_public_urls"]
    paper_group = next(item for item in duplicate_urls if item["normalized_public_url"] == "https://example.org/paper")
    assert paper_group["count"] == 2
    registry_group = next(
        item for item in duplicate_urls if item["normalized_public_url"] == "https://registry.example/study"
    )
    assert registry_group["count"] == 2

    assert health["cross_assessment_source_id_overlaps"] == [
        {
            "source_id": "SRC-X",
            "count": 2,
            "records": [
                {"assessment_id": "LEGACY-1", "evidence_id": "EV-SHARED"},
                {"assessment_id": "CURRENT-1", "evidence_id": "EV-C1"},
            ],
        }
    ]
    by_assessment = {row["assessment_id"]: row for row in health["by_assessment"]}
    assert by_assessment["LEGACY-1"]["evidence_count"] == 4
    assert by_assessment["LEGACY-1"]["link_count"] == 4
    assert by_assessment["LEGACY-1"]["orphan_evidence_count"] == 1
    assert by_assessment["CURRENT-1"]["link_count"] == 3


def test_duplicate_and_dangling_evidence_are_explicit() -> None:
    assessment = _legacy()
    assessment["evidence_register"].append(dict(assessment["evidence_register"][0]))
    assessment["requirement_findings"][0]["evidence_ids"].append("EV-MISSING")
    package = normalize_assessment_evidence(assessment)
    assert package["duplicate_evidence_ids"] == [{"evidence_id": "EV-URL", "count": 2}]
    assert package["dangling_evidence_ids"] == ["EV-MISSING"]

    analysis = build_assessment_evidence_analysis([assessment])
    assert analysis["health"]["duplicate_evidence_ids"] == [
        {"assessment_id": "LEGACY-1", "evidence_id": "EV-URL", "count": 2}
    ]
    assert analysis["health"]["dangling_evidence_links"] == [
        {"assessment_id": "LEGACY-1", "evidence_id": "EV-MISSING"}
    ]


def test_invalid_assessment_inputs_fail_clearly() -> None:
    with pytest.raises(ValueError, match="must be a JSON object"):
        normalize_assessment_evidence([], ordinal=2)
    with pytest.raises(ValueError, match="no requirement_findings"):
        normalize_assessment_evidence({"assessment_metadata": {"assessment_id": "EMPTY"}})
    with pytest.raises(ValueError, match=r"requirement_findings\[0\]"):
        normalize_assessment_evidence(
            {
                "assessment_metadata": {"assessment_id": "BAD-FINDING"},
                "evidence_register": [],
                "requirement_findings": ["bad"],
            }
        )
    with pytest.raises(ValueError, match=r"evidence\[0\]"):
        normalize_assessment_evidence(
            {
                "assessment_metadata": {"assessment_id": "BAD-EVIDENCE"},
                "evidence_register": ["bad"],
                "requirement_findings": [{"requirement_id": "NK-01-R01", "evidence_ids": []}],
            }
        )
    with pytest.raises(ValueError, match="At least one"):
        build_assessment_evidence_analysis([])
    with pytest.raises(ValueError, match="unique assessment_id"):
        build_assessment_evidence_analysis([_legacy(), _legacy()])


def test_outputs_are_flat_machine_readable_and_human_readable(tmp_path: Path) -> None:
    analysis = build_assessment_evidence_analysis([_legacy(), _current()])
    markdown = render_evidence_health_markdown(analysis)
    assert "# NeuroAI assessment evidence health" in markdown
    assert "Evidence records: 6" in markdown
    assert "Evidence→requirement links: 7" in markdown
    assert "LEGACY-1" in markdown

    outputs = write_assessment_evidence_outputs(analysis, tmp_path / "evidence")
    for path in outputs.values():
        assert Path(path).is_file()

    jsonl_rows = [
        json.loads(line)
        for line in Path(outputs["evidence_jsonl"]).read_text(encoding="utf-8").splitlines()
    ]
    assert len(jsonl_rows) == 6
    assert jsonl_rows[0]["raw"]

    with Path(outputs["evidence_csv"]).open(newline="", encoding="utf-8") as handle:
        evidence_rows = list(csv.DictReader(handle))
    assert len(evidence_rows) == 6
    assert "raw" not in evidence_rows[0]

    with Path(outputs["links_csv"]).open(newline="", encoding="utf-8") as handle:
        link_rows = list(csv.DictReader(handle))
    assert len(link_rows) == 7
    assert {row["assessment_id"] for row in link_rows} == {"LEGACY-1", "CURRENT-1"}

    health = json.loads(Path(outputs["health_json"]).read_text(encoding="utf-8"))
    assert health["metadata"]["evidence_count"] == 6
    assert health["health"]["orphan_evidence_count"] == 1
