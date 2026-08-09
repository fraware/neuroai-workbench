from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench import data_cli
from neuroai_workbench.data_search import (
    SEARCH_SCORE_NOTE,
    build_search_index,
    render_search_markdown,
    search_index,
    write_search_outputs,
)


def _assessment() -> dict[str, Any]:
    return {
        "assessment_metadata": {
            "assessment_id": "ASSESS-1",
            "title": "Neuro System assessment",
            "instrument_version": "4.2",
            "evidence_cutoff": "2026-08-01",
        },
        "system_profile": {"system_name": "Neuro System"},
        "evidence_register": [
            {
                "evidence_id": "EV-1",
                "title": "Adaptive decoder trial",
                "source": "Journal of NeuroAI",
                "evidence_class": "PEER_REVIEWED",
                "url_or_path": "https://example.org/adaptive",
                "published": "2026-07-10",
                "retrieval_date": "2026-08-01",
                "evidence_state": "CURRENT_SOURCE_RETRIEVED",
            },
            {
                "evidence_id": "EV-2",
                "title": "Old decoder study",
                "source": "Archive",
                "evidence_class": "PEER_REVIEWED",
                "url_or_path": "https://example.org/old",
                "published": "2026-01-05",
                "retrieval_date": "2026-08-07",
            },
        ],
        "requirement_findings": [
            {
                "requirement_id": "NK-08-R02",
                "module_id": "NK-08",
                "module": "Evidence maturity",
                "priority": "P0",
                "finding_status": "PARTIAL",
                "evidence_ids": ["EV-1"],
            },
            {
                "requirement_id": "NK-05-R01",
                "module_id": "NK-05",
                "module": "Validation",
                "priority": "P1",
                "finding_status": "PASS",
                "evidence_ids": ["EV-2"],
            },
        ],
    }


def _release() -> dict[str, Any]:
    return {
        "metadata": {"version": "v-test", "effective_as_of": "2026-08-01"},
        "organizations": [
            {
                "organization_id": "ORG-1",
                "canonical_name": "NK-08-R02 Research Group",
                "status": "ACTIVE",
            },
            {
                "organization_id": "ORG-A",
                "canonical_name": "Twin Lab",
            },
            {
                "organization_id": "ORG-B",
                "canonical_name": "Twin Lab",
            },
        ],
        "sources": [
            {
                "source_id": "SRC-NEW",
                "title": "Adaptive decoder regulatory notice",
                "publisher": "Regulator",
                "source_class": "REGULATORY_RECORD",
                "publication_date": "2026-07-20",
                "retrieved_at": "2026-08-04",
                "status": "CURRENT",
            },
            {
                "source_id": "SRC-RETRIEVED",
                "title": "Fresh retrieval old publication",
                "publisher": "Archive",
                "source_class": "PEER_REVIEWED",
                "publication_date": "2026-01-01",
                "retrieved_at": "2026-08-07",
                "status": "CURRENT",
            },
        ],
        "events": [
            {
                "event_id": "EVT-1",
                "title": "Adaptive decoder milestone",
                "system": "Neuro System",
                "event_date": "2026-07-25",
                "status": "CONFIRMED",
            }
        ],
    }


def _registry() -> list[dict[str, Any]]:
    return [
        {
            "monitor_id": "MON-1",
            "source_id": "SRC-MON",
            "publisher": "Monitor Publisher",
            "source_class": "OFFICIAL_COMPANY_PAGE",
            "url": "https://example.org/monitor",
            "last_successful_retrieval": "2026-08-06",
            "current_status": "BASELINE_REGISTERED",
        }
    ]


def _agenda() -> list[dict[str, Any]]:
    return [
        {
            "rank": 1,
            "requirement_id": "NK-08-R02",
            "module_id": "NK-08",
            "module": "Evidence maturity",
            "priority": "P0",
            "urgency": "NOW",
            "recommended_focus": "ESTABLISH_BASELINE_EVIDENCE",
            "status": "OPEN",
        }
    ]


def _unified_index() -> list[dict[str, Any]]:
    return build_search_index(
        release=_release(),
        registry=_registry(),
        assessments=[_assessment()],
        evidence_priorities=[_agenda()],
    )


def test_unified_index_exposes_typed_cross_origin_records() -> None:
    index = _unified_index()
    record_types = {str(item["record_type"]) for item in index}
    assert {
        "organizations",
        "sources",
        "events",
        "source_monitor",
        "assessment_evidence",
        "assessment_finding",
        "evidence_priority",
    } <= record_types

    evidence = next(item for item in index if item["record_id"] == "ASSESS-1:EV-1")
    assert evidence["origin"] == "assessment"
    assert evidence["assessment_id"] == "ASSESS-1"
    assert evidence["system_name"] == "Neuro System"
    assert evidence["substantive_date"] == "2026-07-10"
    assert evidence["retrieval_date"] == "2026-08-01"
    assert evidence["source_class"] == "PEER_REVIEWED"

    finding = next(item for item in index if item["record_id"] == "ASSESS-1:NK-08-R02")
    assert finding["requirement_id"] == "NK-08-R02"
    assert finding["module_id"] == "NK-08"
    assert finding["priority"] == "P0"
    assert finding["status"] == "PARTIAL"


def test_exact_requirement_id_precedes_mentions_across_origins() -> None:
    results = search_index(_unified_index(), "NK-08-R02")
    assert {item["record_type"] for item in results[:2]} == {"assessment_finding", "evidence_priority"}
    org_score = next(item["score"] for item in results if item["record_id"] == "ORG-1")
    assert all(item["score"] > org_score for item in results[:2])
    explanation = results[0]["score_explanation"]
    requirement = next(item for item in explanation if item["field"] == "requirement_id")
    assert requirement["weight"] == 16
    assert "EXACT_VALUE" in requirement["signals"]
    assert SEARCH_SCORE_NOTE.startswith("Score is a deterministic lexical retrieval score")


def test_exact_scoped_record_id_is_searchable() -> None:
    results = search_index(_unified_index(), "ASSESS-1:EV-1")
    assert results[0]["record_id"] == "ASSESS-1:EV-1"
    assert results[0]["record_type"] == "assessment_evidence"
    assert "record_id" in results[0]["matched_fields"]
    record_id_score = next(item for item in results[0]["score_explanation"] if item["field"] == "record_id")
    assert record_id_score["weight"] == 12
    assert "EXACT_VALUE" in record_id_score["signals"]


def test_filters_apply_to_typed_metadata_case_insensitively() -> None:
    index = _unified_index()
    by_assessment = search_index(index, "Neuro", assessments={"assess-1"})
    assert by_assessment
    assert {item["assessment_id"] for item in by_assessment} == {"ASSESS-1"}

    by_system = search_index(index, "Adaptive", systems={"neuro system"})
    assert {item["record_type"] for item in by_system} == {"assessment_evidence", "events"}

    by_class = search_index(index, "Adaptive", source_classes={"peer_reviewed"})
    assert [item["record_id"] for item in by_class] == ["ASSESS-1:EV-1"]

    by_priority = search_index(index, "NK", priorities={"p0"})
    assert {item["record_type"] for item in by_priority} == {"assessment_finding", "evidence_priority"}

    by_status = search_index(index, "NK-08-R02", statuses={"partial"})
    assert [item["record_type"] for item in by_status] == ["assessment_finding"]

    by_type = search_index(index, "Adaptive", record_types={"sources"})
    assert [item["record_id"] for item in by_type] == ["SRC-NEW"]


def test_date_filters_use_substantive_dates_only() -> None:
    index = _unified_index()
    recent = search_index(index, "Adaptive", after="2026-07-01")
    ids = {item["record_id"] for item in recent}
    assert "ASSESS-1:EV-1" in ids
    assert "SRC-NEW" in ids
    assert "EVT-1" in ids

    retrieved_only = search_index(index, "Fresh", after="2026-07-01")
    assert retrieved_only == []
    monitor = search_index(index, "Monitor", after="2026-07-01")
    assert monitor == []

    before = search_index(index, "Old decoder", before="2026-02-01")
    assert {item["record_id"] for item in before} == {"ASSESS-1:EV-2", "SRC-RETRIEVED"}
    assert all(item["substantive_date"] < "2026-02-01" for item in before)


def test_date_filters_fail_closed_on_invalid_or_inverted_windows() -> None:
    index = _unified_index()
    with pytest.raises(ValueError, match="Invalid after date"):
        search_index(index, "Adaptive", after="July")
    with pytest.raises(ValueError, match="earlier"):
        search_index(index, "Adaptive", after="2026-08-01", before="2026-08-01")


def test_deterministic_ties_and_release_only_compatibility() -> None:
    release_index = build_search_index(release=_release())
    twins = search_index(release_index, "Twin Lab")
    assert [item["record_id"] for item in twins[:2]] == ["ORG-A", "ORG-B"]
    assert twins[0]["score"] == twins[1]["score"]

    source = search_index(release_index, "SRC-NEW")
    assert source[0]["record_id"] == "SRC-NEW"
    assert source[0]["origin"] == "release"
    assert search_index(release_index, "no-such-token") == []


def test_priority_input_shapes_and_invalid_release_fail_closed() -> None:
    wrapped = build_search_index(evidence_priorities=[{"priorities": _agenda()}])
    assert [item["record_type"] for item in wrapped] == ["evidence_priority"]
    direct = build_search_index(evidence_priorities=[_agenda()[0]])
    assert [item["record_id"] for item in direct] == ["NK-08-R02"]
    with pytest.raises(ValueError, match="Evidence-priority"):
        build_search_index(evidence_priorities=[{"metadata": {"version": "x"}}])
    with pytest.raises(ValueError, match="JSON object"):
        build_search_index(release=[])


def test_outputs_preserve_typed_metadata_and_score_semantics(tmp_path: Path) -> None:
    results = search_index(_unified_index(), "Adaptive")
    markdown = render_search_markdown("Adaptive", results)
    assert SEARCH_SCORE_NOTE in markdown
    assert "Origin" in markdown
    outputs = write_search_outputs("Adaptive", results, tmp_path / "outputs")
    payload = json.loads(Path(outputs["json"]).read_text(encoding="utf-8"))
    assert payload["scoring_note"] == SEARCH_SCORE_NOTE
    assert payload["results"][0]["score_explanation"]
    csv_text = Path(outputs["csv"]).read_text(encoding="utf-8")
    assert csv_text.startswith("rank,record_type,record_id,title,origin,assessment_id,system_name,substantive_date")
    assert "score_explanation" in csv_text.splitlines()[0]


def test_cli_searches_assessment_inputs_with_required_filter_names(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    release_path = tmp_path / "release.json"
    assessment_path = tmp_path / "assessment.json"
    agenda_path = tmp_path / "agenda.json"
    release_path.write_text(json.dumps(_release()), encoding="utf-8")
    assessment_path.write_text(json.dumps(_assessment()), encoding="utf-8")
    agenda_path.write_text(json.dumps(_agenda()), encoding="utf-8")
    output_dir = tmp_path / "search"

    code = data_cli.main(
        [
            "search",
            "Adaptive",
            "--release",
            str(release_path),
            "--assessment-file",
            str(assessment_path),
            "--research-agenda",
            str(agenda_path),
            "--assessment",
            "ASSESS-1",
            "--source-class",
            "PEER_REVIEWED",
            "--after",
            "2026-07-01",
            "--output-dir",
            str(output_dir),
        ]
    )
    assert code == 0
    stdout = capsys.readouterr().out
    assert "indexed" in stdout
    payload = json.loads((output_dir / "search-results.json").read_text(encoding="utf-8"))
    assert [item["record_id"] for item in payload["results"]] == ["ASSESS-1:EV-1"]
    assert payload["results"][0]["substantive_date"] == "2026-07-10"


def test_cli_search_requires_any_index_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = data_cli.main(["search", "Adaptive", "--output-dir", str(tmp_path)])
    assert code == 2
    assert "release, registry, assessment, or evidence-priority" in capsys.readouterr().err
