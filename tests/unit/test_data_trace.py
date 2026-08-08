from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench import data_cli
from neuroai_workbench.data_trace import render_trace_markdown, trace_propagation, write_trace_outputs


def _release() -> dict[str, Any]:
    return {
        "metadata": {"version": "v-test"},
        "organizations": [
            {
                "organization_id": "ORG-1",
                "canonical_name": "Meta AI",
                "source_ids": ["SRC-1"],
            }
        ],
        "representative_model_records": [
            {
                "model_id": "MDL-1",
                "name": "Brain2Qwerty v2",
                "developer": "Meta AI",
                "source_ids": ["SRC-1", "SRC-2"],
            }
        ],
        "sources": [
            {
                "source_id": "SRC-1",
                "title": "Brain2Qwerty v2 announcement",
                "publisher": "Meta AI",
                "source_class": "OFFICIAL_RESEARCH_ANNOUNCEMENT",
                "url": "HTTPS://AI.META.COM/blog/brain2qwerty/",
            },
            {
                "source_id": "SRC-2",
                "title": "Brain2Qwerty preprint",
                "publisher": "Meta AI",
                "source_class": "PREPRINT",
                "url": "https://example.org/preprint",
                "sha256": "ABC123",
            },
            {
                "source_id": "SRC-3",
                "title": "Unrelated source",
                "publisher": "Other",
                "source_class": "OFFICIAL_PAGE",
                "url": "https://example.org/unmatched",
            },
        ],
    }


def _legacy_assessment() -> dict[str, Any]:
    return {
        "assessment_metadata": {
            "assessment_id": "B2Q-v4.1.3",
            "title": "Brain2Qwerty assessment",
        },
        "system_profile": {"system_name": "Brain2Qwerty"},
        "evidence_register": [
            {
                "evidence_id": "EV-URL",
                "title": "Meta announcement",
                "url_or_path": "https://ai.meta.com/blog/brain2qwerty",
            },
            {
                "evidence_id": "EV-SHA",
                "title": "Local exact preprint",
                "url_or_path": "/controlled/preprint.pdf",
                "checksum": "abc123",
            },
            {
                "evidence_id": "EV-EXTERNAL",
                "title": "External evidence absent from observatory",
                "url_or_path": "https://journal.example/new-evidence",
            },
        ],
        "requirement_findings": [
            {
                "requirement_id": "NK-01-R01",
                "finding_status": "PASS",
                "evidence_ids": ["EV-URL"],
            },
            {
                "requirement_id": "NK-01-R02",
                "finding_status": "PARTIAL",
                "evidence_ids": ["EV-URL", "EV-SHA"],
            },
            {
                "requirement_id": "NK-02-R01",
                "finding_status": "PARTIAL",
                "evidence_ids": ["EV-SHA"],
            },
        ],
    }


def _current_assessment() -> dict[str, Any]:
    return {
        "metadata": {"assessment_id": "CURRENT-1", "title": "Current assessment"},
        "system": {"system_name": "Current System"},
        "sources": [
            {
                "source_id": "EV-CURRENT",
                "title": "Current source",
                "url": "https://example.org/unmatched",
            }
        ],
        "requirement_findings": [
            {
                "requirement_id": "NK-03-R01",
                "status": "PASS",
                "evidence_ids": ["EV-CURRENT"],
            }
        ],
    }


def test_trace_links_url_checksum_and_requirements() -> None:
    trace = trace_propagation(_release(), [_legacy_assessment()])
    assert trace["metadata"]["release_version"] == "v-test"
    assert trace["summary"]["sources_traced_to_assessment_evidence"] == 2
    assert trace["summary"]["sources_traced_to_requirements"] == 2
    assert trace["summary"]["sources_untraced"] == 1

    by_source = {row["source_id"]: row for row in trace["source_traces"]}
    src1 = by_source["SRC-1"]
    assert src1["trace_state"] == "TRACED_TO_REQUIREMENTS"
    assert src1["requirement_ids"] == ["NK-01-R01", "NK-01-R02"]
    assert src1["assessment_paths"][0]["match_rule"] == "URL"

    src2 = by_source["SRC-2"]
    assert src2["requirement_ids"] == ["NK-01-R02", "NK-02-R01"]
    assert src2["assessment_paths"][0]["match_rule"] == "CHECKSUM"
    assert by_source["SRC-3"]["trace_state"] == "UNTRACED"


def test_trace_rolls_source_paths_up_to_model_and_other_records() -> None:
    trace = trace_propagation(_release(), [_legacy_assessment()])
    model = next(row for row in trace["record_traces"] if row["record_id"] == "MDL-1")
    assert model["assessment_ids"] == ["B2Q-v4.1.3"]
    assert model["requirement_ids"] == ["NK-01-R01", "NK-01-R02", "NK-02-R01"]
    assert model["untraced_source_ids"] == []
    assert model["trace_state"] == "TRACED_TO_REQUIREMENTS"

    organization = next(row for row in trace["record_traces"] if row["record_id"] == "ORG-1")
    assert organization["requirement_ids"] == ["NK-01-R01", "NK-01-R02"]


def test_trace_surfaces_unmatched_public_assessment_evidence() -> None:
    trace = trace_propagation(_release(), [_legacy_assessment()])
    unmatched = trace["unmatched_assessment_evidence"]
    assert [row["evidence_id"] for row in unmatched] == ["EV-EXTERNAL"]
    assert unmatched[0]["requirement_ids"] == []


def test_trace_supports_current_assessment_shape() -> None:
    trace = trace_propagation(_release(), [_legacy_assessment(), _current_assessment()])
    by_source = {row["source_id"]: row for row in trace["source_traces"]}
    assert by_source["SRC-3"]["requirement_ids"] == ["NK-03-R01"]
    current = next(row for row in trace["assessments"] if row["assessment_id"] == "CURRENT-1")
    assert current["matched_observatory_evidence_count"] == 1
    assert current["linked_requirement_ids"] == ["NK-03-R01"]


def test_trace_reports_ambiguous_observatory_urls_without_fuzzy_merge() -> None:
    release = _release()
    release["sources"].append(
        {
            "source_id": "SRC-4",
            "title": "Duplicate URL representation",
            "url": "https://ai.meta.com/blog/brain2qwerty/",
        }
    )
    trace = trace_propagation(release, [_legacy_assessment()])
    assert trace["ambiguous_source_urls"] == [
        {
            "url": "https://ai.meta.com/blog/brain2qwerty",
            "source_ids": ["SRC-1", "SRC-4"],
            "count": 2,
        }
    ]
    by_source = {row["source_id"]: row for row in trace["source_traces"]}
    assert by_source["SRC-4"]["assessment_paths"]
    assert trace["metadata"]["fuzzy_matching"] is False


def test_trace_rejects_invalid_and_conflicting_inputs() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        trace_propagation([], [_legacy_assessment()])
    with pytest.raises(ValueError, match="At least one"):
        trace_propagation(_release(), [])
    with pytest.raises(ValueError, match="Duplicate assessment_id"):
        trace_propagation(_release(), [_legacy_assessment(), _legacy_assessment()])

    release = _release()
    release["sources"].append(
        {
            "source_id": "SRC-1",
            "url": "https://different.example/source",
        }
    )
    with pytest.raises(ValueError, match="Conflicting duplicate source_id"):
        trace_propagation(release, [_legacy_assessment()])


def test_trace_outputs_are_deterministic_and_readable(tmp_path: Path) -> None:
    trace = trace_propagation(_release(), [_legacy_assessment()])
    markdown = render_trace_markdown(trace)
    assert "# NeuroAI propagation trace" in markdown
    assert "SRC-1" in markdown
    assert "EV-EXTERNAL" in markdown

    outputs = write_trace_outputs(trace, tmp_path / "trace")
    assert Path(outputs["json"]).is_file()
    assert Path(outputs["sources_csv"]).read_text(encoding="utf-8").startswith("source_id,title")
    assert Path(outputs["records_csv"]).read_text(encoding="utf-8").startswith("record_type,record_id")
    assert Path(outputs["markdown"]).read_text(encoding="utf-8") == markdown


def test_trace_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    release = tmp_path / "release.json"
    assessment = tmp_path / "assessment.json"
    release.write_text(json.dumps(_release()), encoding="utf-8")
    assessment.write_text(json.dumps(_legacy_assessment()), encoding="utf-8")
    output = tmp_path / "out"

    assert (
        data_cli.main(
            [
                "trace",
                "--release",
                str(release),
                "--assessment",
                str(assessment),
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )
    stdout = capsys.readouterr().out
    assert "Traced to assessment evidence: 2" in stdout
    assert "through to requirements: 2" in stdout
    assert (output / "propagation-trace.json").is_file()


def test_trace_cli_rejects_missing_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing.json"
    assessment = tmp_path / "assessment.json"
    assessment.write_text(json.dumps(_legacy_assessment()), encoding="utf-8")
    assert (
        data_cli.main(
            [
                "trace",
                "--release",
                str(missing),
                "--assessment",
                str(assessment),
            ]
        )
        == 2
    )
    assert "Input not found" in capsys.readouterr().err
