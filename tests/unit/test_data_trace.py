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
        "organizations": [{"organization_id": "ORG-1", "canonical_name": "Meta AI", "source_ids": ["SRC-1"]}],
        "representative_model_records": [
            {
                "model_id": "MDL-1",
                "name": "Brain2Qwerty v2",
                "developer": "Meta AI",
                "source_ids": ["SRC-1", "SRC-2", "SRC-4"],
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
            {
                "source_id": "SRC-4",
                "title": "Assessment-evidence-only source",
                "publisher": "Registry",
                "source_class": "TRIAL_REGISTRY",
                "url": "https://example.org/evidence-only",
            },
        ],
        "delta": {
            "market_events": [{"event_id": "EVT-1", "system": "Brain2Qwerty", "source_ids": ["SRC-1", "SRC-X"]}],
            "new_sources": [
                {
                    "source_id": "SRC-5",
                    "title": "Successor source",
                    "publisher": "Meta AI",
                    "source_class": "OFFICIAL_PAGE",
                    "url": "https://example.org/successor",
                }
            ],
        },
    }


def _legacy_assessment() -> dict[str, Any]:
    return {
        "assessment_metadata": {"assessment_id": "B2Q-v4.1.3", "title": "Brain2Qwerty assessment"},
        "system_profile": {"system_name": "Brain2Qwerty"},
        "evidence_register": [
            {
                "evidence_id": "EV-SOURCE-ID",
                "title": "Exact source namespace",
                "source_ids": ["SRC-1"],
                "url_or_path": "https://different.example/same-source",
            },
            {
                "evidence_id": "EV-SHA",
                "title": "Local exact preprint",
                "url_or_path": "/controlled/preprint.pdf",
                "checksum": "abc123",
            },
            {
                "evidence_id": "EV-BOTH",
                "title": "URL and checksum",
                "url_or_path": "https://example.org/preprint",
                "checksum": "ABC123",
            },
            {
                "evidence_id": "EV-ONLY",
                "title": "Matched evidence not cited by a requirement",
                "url_or_path": "https://example.org/evidence-only",
            },
            {
                "evidence_id": "EV-EXTERNAL",
                "title": "External evidence absent from observatory",
                "url_or_path": "https://journal.example/new-evidence",
            },
            {"evidence_id": "EV-LOCAL", "title": "Local only", "url_or_path": "/controlled/local.txt"},
            "ignore-me",
        ],
        "requirement_findings": [
            {"requirement_id": "NK-01-R01", "finding_status": "PASS", "evidence_ids": ["EV-SOURCE-ID"]},
            {
                "requirement_id": "NK-01-R02",
                "finding_status": "PARTIAL",
                "evidence_ids": ["EV-SOURCE-ID", "EV-SHA"],
            },
            {"requirement_id": "NK-02-R01", "finding_status": "PARTIAL", "evidence_ids": ["EV-SHA"]},
            {"requirement_id": "NK-02-R02", "finding_status": "PARTIAL", "evidence_ids": ["EV-BOTH"]},
            "ignore-me",
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
                "source_ids": ["SRC-3"],
                "url": "https://different.example/current",
            }
        ],
        "requirement_findings": [{"requirement_id": "NK-03-R01", "status": "PASS", "evidence_ids": ["EV-CURRENT"]}],
    }


def test_trace_prefers_explicit_source_ids_and_links_requirements() -> None:
    trace = trace_propagation(_release(), [_legacy_assessment()])
    by_source = {row["source_id"]: row for row in trace["source_traces"]}

    assert trace["metadata"]["matching"][0] == "EXACT_SOURCE_ID"
    assert by_source["SRC-1"]["assessment_paths"][0]["match_rule"] == "SOURCE_ID"
    assert by_source["SRC-1"]["requirement_ids"] == ["NK-01-R01", "NK-01-R02"]
    assert by_source["SRC-2"]["requirement_ids"] == ["NK-01-R02", "NK-02-R01", "NK-02-R02"]
    assert {path["match_rule"] for path in by_source["SRC-2"]["assessment_paths"]} == {
        "CHECKSUM",
        "URL_AND_CHECKSUM",
    }
    assert by_source["SRC-4"]["trace_state"] == "TRACED_TO_ASSESSMENT_EVIDENCE"
    assert by_source["SRC-4"]["requirement_ids"] == []
    assert by_source["SRC-5"]["trace_state"] == "UNTRACED"


def test_trace_rolls_source_paths_up_to_records_and_marks_partial_sources() -> None:
    trace = trace_propagation(_release(), [_legacy_assessment()])
    model = next(row for row in trace["record_traces"] if row["record_id"] == "MDL-1")
    assert model["assessment_ids"] == ["B2Q-v4.1.3"]
    assert model["requirement_ids"] == ["NK-01-R01", "NK-01-R02", "NK-02-R01", "NK-02-R02"]
    assert model["untraced_source_ids"] == []
    assert model["trace_state"] == "TRACED_TO_REQUIREMENTS"

    event = next(row for row in trace["record_traces"] if row["record_id"] == "EVT-1")
    assert event["record_type"] == "delta.market_events"
    assert event["traced_source_count"] == 1
    assert event["untraced_source_ids"] == ["SRC-X"]
    assert event["trace_state"] == "TRACED_TO_REQUIREMENTS"


def test_trace_surfaces_only_actionable_unmatched_assessment_evidence() -> None:
    trace = trace_propagation(_release(), [_legacy_assessment()])
    unmatched = trace["unmatched_assessment_evidence"]
    assert [row["evidence_id"] for row in unmatched] == ["EV-EXTERNAL"]
    assert all(row["evidence_id"] != "EV-LOCAL" for row in unmatched)


def test_trace_supports_current_assessment_shape_and_source_id_namespace() -> None:
    trace = trace_propagation(_release(), [_legacy_assessment(), _current_assessment()])
    by_source = {row["source_id"]: row for row in trace["source_traces"]}
    assert by_source["SRC-3"]["requirement_ids"] == ["NK-03-R01"]
    assert by_source["SRC-3"]["assessment_paths"][0]["match_rule"] == "SOURCE_ID"
    current = next(row for row in trace["assessments"] if row["assessment_id"] == "CURRENT-1")
    assert current["matched_observatory_evidence_count"] == 1
    assert current["linked_requirement_ids"] == ["NK-03-R01"]


def test_trace_reports_ambiguous_urls_without_fuzzy_merge() -> None:
    release = _release()
    release["sources"].append(
        {"source_id": "SRC-6", "title": "Duplicate URL representation", "url": "https://ai.meta.com/blog/brain2qwerty/"}
    )
    trace = trace_propagation(release, [_legacy_assessment()])
    assert trace["ambiguous_source_urls"] == [
        {
            "url": "https://ai.meta.com/blog/brain2qwerty",
            "source_ids": ["SRC-1", "SRC-6"],
            "count": 2,
        }
    ]
    assert trace["metadata"]["fuzzy_matching"] is False


def test_trace_accepts_identical_duplicate_source_and_rejects_conflict() -> None:
    release = _release()
    release["delta"]["extra_sources"] = [dict(release["sources"][0])]
    trace = trace_propagation(release, [_legacy_assessment()])
    assert sum(row["source_id"] == "SRC-1" for row in trace["source_traces"]) == 1

    release = _release()
    release["delta"]["extra_sources"] = [{"source_id": "SRC-1", "url": "https://different.example/source"}]
    with pytest.raises(ValueError, match="Conflicting duplicate source_id"):
        trace_propagation(release, [_legacy_assessment()])


def test_trace_rejects_invalid_assessments_and_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        trace_propagation([], [_legacy_assessment()])
    with pytest.raises(ValueError, match="At least one"):
        trace_propagation(_release(), [])
    with pytest.raises(ValueError, match="Assessment 0"):
        trace_propagation(_release(), ["bad"])
    with pytest.raises(ValueError, match="Duplicate assessment_id"):
        trace_propagation(_release(), [_legacy_assessment(), _legacy_assessment()])


def test_trace_outputs_and_empty_markdown_paths(tmp_path: Path) -> None:
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

    empty = {
        "metadata": {"release_version": "empty", "assessment_count": 1, "source_count": 0},
        "summary": {},
        "source_traces": [],
        "unmatched_assessment_evidence": [],
    }
    empty_markdown = render_trace_markdown(empty)
    assert "No exact cross-layer matches" in empty_markdown
    assert "No unmatched public/hashed assessment evidence" in empty_markdown


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
    assert "Propagation trace:" in stdout
    assert "through to requirements:" in stdout
    assert (output / "propagation-trace.json").is_file()


def test_trace_cli_rejects_missing_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing.json"
    assessment = tmp_path / "assessment.json"
    assessment.write_text(json.dumps(_legacy_assessment()), encoding="utf-8")
    assert data_cli.main(["trace", "--release", str(missing), "--assessment", str(assessment)]) == 2
    assert "Input not found" in capsys.readouterr().err
