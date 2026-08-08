from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench import data_cli
from neuroai_workbench.data_health import (
    as_of_date,
    build_data_health,
    normalize_url,
    parse_date,
    profile_registry,
    profile_release,
    registry_records,
    render_data_health_markdown,
    write_data_health_outputs,
)
from neuroai_workbench.data_search import (
    build_search_index,
    render_search_markdown,
    search_index,
    write_search_outputs,
)


def _registry() -> list[dict[str, Any]]:
    return [
        {
            "monitor_id": "MON-1",
            "source_id": "SRC-1",
            "url": "https://example.org/current/",
            "publisher": "Example Lab",
            "source_class": "OFFICIAL_COMPANY_PAGE",
            "cadence": "WEEKLY",
            "last_successful_retrieval": "2026-08-04",
            "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
            "baseline_verification_state": "CURRENT_VERIFIED",
            "current_status": "BASELINE_REGISTERED",
        },
        {
            "monitor_id": "MON-2",
            "source_id": "SRC-2",
            "url": "https://example.org/due",
            "publisher": "FDA",
            "source_class": "REGULATORY_RECORD",
            "cadence": "WEEKLY",
            "last_successful_retrieval": "2026-07-29",
            "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
            "baseline_verification_state": "CURRENT_VERIFIED",
            "current_status": "BASELINE_REGISTERED",
        },
        {
            "monitor_id": "MON-3",
            "source_id": "SRC-3",
            "url": "https://example.org/stale",
            "publisher": "Clinical Registry",
            "source_class": "TRIAL_REGISTRY",
            "cadence": "WEEKLY",
            "last_successful_retrieval": "2026-07-01",
            "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
            "baseline_verification_state": "CURRENT_PARTIAL",
            "current_status": "BASELINE_REGISTERED",
        },
        {
            "monitor_id": "MON-4",
            "source_id": "SRC-4",
            "url": "https://example.org/never",
            "publisher": "Journal",
            "source_class": "PEER_REVIEWED_PUBLICATION",
            "cadence": "MONTHLY",
            "last_successful_retrieval": None,
            "baseline_evidence_state": "UNRESOLVED",
            "baseline_verification_state": "NOT_VERIFIED",
            "current_status": "BASELINE_REGISTERED",
        },
        {
            "monitor_id": "MON-5",
            "source_id": "SRC-5",
            "url": "HTTPS://EXAMPLE.ORG/current",
            "publisher": "Example Lab",
            "source_class": "OFFICIAL_COMPANY_PAGE",
            "cadence": "ON_CHANGE",
            "last_successful_retrieval": "2026-08-09",
            "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
            "baseline_verification_state": "CURRENT_VERIFIED",
            "current_status": "BASELINE_REGISTERED",
        },
    ]


def _full_release() -> dict[str, Any]:
    return {
        "metadata": {
            "version": "v-test",
            "status": "CONTROLLED",
            "effective_as_of": "2026-07-29",
        },
        "organizations": [
            {
                "organization_id": "ORG-1",
                "canonical_name": "Science Corporation",
                "organization_type": "COMPANY",
                "verification_state": "CURRENT_VERIFIED",
                "evidence_state": "CURRENT_SOURCE_RETRIEVED",
                "headquarters_country": "United States",
                "official_url": "https://science.xyz/",
            },
            {
                "organization_id": "ORG-2",
                "canonical_name": "Paradromics",
                "organization_type": "COMPANY",
                "verification_state": "CURRENT_PARTIAL",
                "evidence_state": "CURRENT_PARTIAL",
                "headquarters_country": "United States",
                "official_url": "https://paradromics.com",
            },
        ],
        "sources": [
            {
                "source_id": "SRC-A",
                "publisher": "U.S. Food and Drug Administration",
                "source_class": "REGULATORY_RECORD",
                "title": "FDA PRIMA record",
                "url": "https://fda.gov/prima",
                "evidence_state": "CURRENT_SOURCE_RETRIEVED",
                "verification_state": "CURRENT_VERIFIED",
            },
            {
                "source_id": "SRC-B",
                "publisher": "Science Corporation",
                "source_class": "OFFICIAL_COMPANY_PAGE",
                "title": "PRIMA commercial launch",
                "url": "https://science.xyz/prima",
                "evidence_state": "CURRENT_SOURCE_RETRIEVED",
                "verification_state": "CURRENT_PARTIAL",
            },
        ],
        "representative_model_records": [
            {
                "model_id": "MDL-1",
                "name": "Chiral",
                "developer": "Synchron",
                "record_type": "MODEL_ROADMAP",
                "verification_state": "ROADMAP_ONLY",
            }
        ],
    }


def _compact_release() -> dict[str, Any]:
    return {
        "metadata": {
            "version": "v1.7",
            "status": "CONTROLLED_SUCCESSOR_SNAPSHOT",
            "effective_as_of": "2026-07-29",
        },
        "successor_effective_counts": {"organizations": 153, "source_records": 248},
        "delta": {
            "regulatory_and_market_events": [
                {
                    "event_id": "REG-16-001",
                    "system": "PRIMA retinal prosthesis",
                    "event_type": "CE_MARK_AND_COMMERCIAL_LAUNCH_ANNOUNCEMENT",
                    "jurisdiction": "European Union / EEA",
                }
            ],
            "model_records": [
                {
                    "model_id": "MDL-16-001",
                    "name": "Chiral",
                    "developer": "Synchron",
                    "verification_state": "ROADMAP_ONLY",
                }
            ],
        },
        "reopening_decisions": [
            {
                "decision_id": "ROP-17-001",
                "object": "PRIMA observatory system record",
                "decision": "REOPENING_EXECUTED_RECORD_UPDATED_OPEN_CONDITIONS",
            }
        ],
        "assessment_successor_delta": {
            "assessment_delta": {
                "assessment_id": "PRIMA-PUBLIC-2026-001",
                "system": "PRIMA retinal prosthesis",
                "decision": "CL-4_NOT_ESTABLISHED",
            }
        },
    }


def test_date_and_url_helpers() -> None:
    assert parse_date("2026-08-08") == date(2026, 8, 8)
    assert parse_date("2026-08-08T10:00:00Z") == date(2026, 8, 8)
    assert parse_date("bad") is None
    assert parse_date(None) is None
    assert as_of_date(date(2026, 8, 8)) == date(2026, 8, 8)
    with pytest.raises(ValueError, match="Invalid as-of"):
        as_of_date("bad")
    assert normalize_url("HTTPS://Example.org/path/#fragment") == "https://example.org/path"
    assert normalize_url("relative/") == "relative"
    assert normalize_url(None) is None


def test_registry_records_accepts_both_shapes_and_rejects_other() -> None:
    rows = _registry()
    assert registry_records(rows) == rows
    assert registry_records({"sources": rows}) == rows
    with pytest.raises(ValueError, match="Source registry"):
        registry_records({"wrong": rows})


def test_registry_health_surfaces_freshness_duplicates_and_attention() -> None:
    profile = profile_registry(_registry(), as_of="2026-08-08")
    assert profile["source_count"] == 5
    assert profile["freshness_counts"] == {
        "CURRENT": 1,
        "DUE": 1,
        "FUTURE_DATE": 1,
        "NEVER_OR_INVALID": 1,
        "STALE": 1,
    }
    assert profile["freshness"][0]["source_id"] == "SRC-3"
    assert profile["freshness"][1]["source_id"] == "SRC-2"
    assert profile["duplicate_urls"][0]["count"] == 2
    assert profile["publisher_distribution"]["Example Lab"] == 2
    assert profile["completeness"]["last_successful_retrieval"]["missing"] == 1
    attention = {(item["record_id"], item["field"]) for item in profile["attention_states"]}
    assert ("SRC-3", "baseline_verification_state") in attention
    assert ("SRC-4", "baseline_evidence_state") in attention


def test_registry_health_unknown_cadence_with_past_date() -> None:
    row = _registry()[0]
    row["cadence"] = "ON_CHANGE"
    profile = profile_registry([row], as_of="2026-08-08")
    assert profile["freshness_counts"] == {"UNKNOWN_CADENCE": 1}


def test_full_release_health_is_explicit() -> None:
    profile = profile_release(_full_release(), as_of="2026-08-08")
    assert profile["effective_age_days"] == 10
    assert profile["organization_count"] == 2
    assert profile["source_count"] == 2
    assert profile["organization_verification_distribution"]["CURRENT_PARTIAL"] == 1
    assert profile["source_class_distribution"]["REGULATORY_RECORD"] == 1
    assert profile["organization_completeness"]["organization_id"]["rate"] == 1.0
    assert profile["duplicate_organization_ids"] == []
    assert profile["source_attention_states"][0]["record_id"] == "SRC-B"


def test_compact_release_health_preserves_effective_counts() -> None:
    profile = profile_release(_compact_release(), as_of="2026-08-08")
    assert profile["effective_age_days"] == 10
    assert profile["organization_count"] == 0
    assert profile["source_count"] == 0
    assert profile["delta_sections"] == {"model_records": 1, "regulatory_and_market_events": 1}
    assert profile["reopening_decision_count"] == 1
    assert profile["successor_effective_counts"]["source_records"] == 248
    with pytest.raises(ValueError, match="JSON object"):
        profile_release([], as_of="2026-08-08")


def test_build_health_requires_input_and_writes_outputs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="At least one"):
        build_data_health(as_of="2026-08-08")
    health = build_data_health(release=_full_release(), registry=_registry(), as_of="2026-08-08")
    assert health["metadata"]["scoring"] == "EXPLICIT_METRICS_ONLY"
    markdown = render_data_health_markdown(health)
    assert "Effective age: 10 day(s)" in markdown
    assert "SRC-3" in markdown
    outputs = write_data_health_outputs(health, tmp_path / "health")
    assert Path(outputs["json"]).is_file()
    assert Path(outputs["markdown"]).is_file()


def test_search_index_covers_full_compact_and_registry() -> None:
    full = build_search_index(release=_full_release(), registry=_registry())
    assert any(item["record_type"] == "organizations" and item["record_id"] == "ORG-1" for item in full)
    assert any(item["record_type"] == "representative_model_records" and item["record_id"] == "MDL-1" for item in full)
    assert sum(item["record_type"] == "source_monitor" for item in full) == 5

    compact = build_search_index(release=_compact_release())
    assert any(item["record_type"] == "delta.regulatory_and_market_events" for item in compact)
    assert any(item["record_type"] == "assessment_successor_delta" for item in compact)
    assert any(item["record_id"] == "ROP-17-001" for item in compact)
    with pytest.raises(ValueError, match="At least one"):
        build_search_index()


def test_search_exact_ids_and_named_entities_rank_high() -> None:
    index = build_search_index(release=_full_release(), registry=_registry())
    by_id = search_index(index, "SRC-A")
    assert by_id[0]["record_id"] == "SRC-A"
    assert "source_id" in by_id[0]["matched_fields"]

    science = search_index(index, "Science Corporation")
    assert science[0]["record_id"] == "ORG-1"
    assert science[0]["title"] == "Science Corporation"
    assert science[0]["score"] > science[-1]["score"]

    fda = search_index(index, "FDA")
    assert any(item["record_id"] == "SRC-2" for item in fda)


def test_search_compact_semantics_and_filtering() -> None:
    index = build_search_index(release=_compact_release())
    prima = search_index(index, "PRIMA retinal", limit=10)
    assert prima[0]["record_type"] == "delta.regulatory_and_market_events"
    only_models = search_index(index, "Chiral", record_types={"delta.model_records"})
    assert [item["record_id"] for item in only_models] == ["MDL-16-001"]
    assert search_index(index, "no-such-token") == []
    with pytest.raises(ValueError, match="searchable text"):
        search_index(index, "   ")
    with pytest.raises(ValueError, match="positive"):
        search_index(index, "PRIMA", limit=0)


def test_search_outputs_are_machine_and_human_readable(tmp_path: Path) -> None:
    index = build_search_index(release=_full_release())
    results = search_index(index, "PRIMA")
    markdown = render_search_markdown("PRIMA", results)
    assert "# NeuroAI search: PRIMA" in markdown
    assert "SRC-A" in markdown or "SRC-B" in markdown
    empty = render_search_markdown("nothing", [])
    assert "No matches" in empty
    outputs = write_search_outputs("PRIMA", results, tmp_path / "search")
    payload = json.loads(Path(outputs["json"]).read_text(encoding="utf-8"))
    assert payload["query"] == "PRIMA"
    assert Path(outputs["csv"]).read_text(encoding="utf-8").startswith("rank,record_type")
    assert Path(outputs["markdown"]).is_file()


def test_data_cli_health_and_search(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    release = tmp_path / "release.json"
    registry = tmp_path / "registry.json"
    release.write_text(json.dumps(_full_release()), encoding="utf-8")
    registry.write_text(json.dumps(_registry()), encoding="utf-8")

    health_out = tmp_path / "health-out"
    assert (
        data_cli.main(
            [
                "health",
                "--release",
                str(release),
                "--registry",
                str(registry),
                "--as-of",
                "2026-08-08",
                "--output-dir",
                str(health_out),
            ]
        )
        == 0
    )
    stdout = capsys.readouterr().out
    assert "effective age: 10 day(s)" in stdout
    assert "due 1" in stdout
    assert (health_out / "data-health.json").is_file()

    search_out = tmp_path / "search-out"
    assert (
        data_cli.main(
            [
                "search",
                "Science Corporation",
                "--release",
                str(release),
                "--registry",
                str(registry),
                "--limit",
                "5",
                "--output-dir",
                str(search_out),
            ]
        )
        == 0
    )
    stdout = capsys.readouterr().out
    assert "ORG-1" in stdout
    assert (search_out / "search-results.csv").is_file()


def test_data_cli_errors_are_clear(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert data_cli.main(["health", "--as-of", "2026-08-08"]) == 2
    assert "Provide --release" in capsys.readouterr().err
    missing = tmp_path / "missing.json"
    assert data_cli.main(["search", "PRIMA", "--release", str(missing)]) == 2
    assert "Input not found" in capsys.readouterr().err
