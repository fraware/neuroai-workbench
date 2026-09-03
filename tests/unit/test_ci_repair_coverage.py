"""Behavioral coverage for post-Wave 7 operational surfaces."""

from __future__ import annotations

import builtins
import json
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

from neuroai_workbench.extraction.corpus_scale import (
    SCALE_CASE_TARGET,
    build_scale_cases,
    build_scale_corpus_document,
    build_scale_manifest,
    load_scale_corpus,
    materialize_scale_corpus,
)
from neuroai_workbench.observatory_lineage import (
    DELTA_SECTIONS,
    detect_v16_package_kind,
    validate_v16_package,
    validate_v16_v17_lineage,
)
from neuroai_workbench.products import excel as excel_module
from neuroai_workbench.shadow_refresh.closure import (
    build_closure_run_results,
    build_public_closure_summary,
    build_source_retry_plan,
    classify_retrieval_failure,
    content_addressed_run_id,
    create_first_capture_candidates,
    handoff_quarantine_sample_to_evaluation,
    list_quarantine_successes,
    publisher_mentions_for_sources,
    record_formal_disposition,
    retry_failed_sources,
    run_offline_entity_sample,
    run_offline_extraction_sample,
)
from neuroai_workbench.util import atomic_write_json, load_json

ROOT = Path(__file__).resolve().parents[2]
LINEAGE_FIXTURES = ROOT / "tests" / "fixtures" / "observatory_lineage"


def test_scale_corpus_generation_materialization_and_loading(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one"):
        build_scale_cases(case_count=0)

    cases = build_scale_cases(case_count=14)
    assert len(cases) == 14
    assert {case["category"] for case in cases} == {
        "REGULATORY_RECORD",
        "CLINICAL_TRIAL",
        "PUBLICATION",
        "COMPANY_ANNOUNCEMENT",
        "OWNERSHIP_FUNDING",
        "SAFETY_WITHDRAWAL",
        "CONTRADICTORY_SOURCE",
    }
    assert cases[0]["annotation"]["expected_fields"][1]["value"].startswith("2026-02-")
    assert cases[1]["annotation"]["expected_fields"][0]["value"] == "SynthTrial Org 2"
    assert cases[2]["annotation"]["expected_fields"][0]["value"] == "SynthPub Lab 3"
    assert cases[3]["annotation"]["expected_fields"][0]["value"] == "SynthDevice Corp 4"
    assert cases[4]["annotation"]["expected_fields"][0]["value"] == "SynthCapital Fund 5"
    assert cases[6]["annotation"]["expected_abstentions"]

    document = build_scale_corpus_document(case_count=14)
    assert document["case_count"] == 14
    assert sum(document["category_counts"].values()) == 14
    assert document["evaluation_lanes"]["primary"] == "captured-response-replay"

    full_manifest = build_scale_manifest(case_count=3)
    empty_manifest = build_scale_manifest(case_count=3, concrete_limit=0)
    assert len(full_manifest["fixtures"]) == 3
    assert empty_manifest["fixtures"] == []

    paths = materialize_scale_corpus(
        tmp_path,
        case_count=SCALE_CASE_TARGET,
        concrete_fixture_count=7,
    )
    loaded = load_scale_corpus(paths["corpus"])
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert loaded["case_count"] == SCALE_CASE_TARGET
    assert len(manifest["fixtures"]) == SCALE_CASE_TARGET
    assert len(list(paths["fixture_dir"].glob("*.capture.json"))) == 7
    assert len(list(paths["fixture_dir"].glob("*.annotation.json"))) == 7
    assert any(item["capture_stub"].startswith("fixtures/") for item in manifest["fixtures"])
    assert any(item["capture_stub"].startswith("corpus:") for item in manifest["fixtures"])


def test_scale_corpus_loader_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_scale_corpus(tmp_path / "missing.json")

    non_object = tmp_path / "non-object.json"
    non_object.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must be an object"):
        load_scale_corpus(non_object)

    too_small = tmp_path / "too-small.json"
    too_small.write_text(json.dumps({"cases": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="at least"):
        load_scale_corpus(too_small)


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ({"failure_class": "TIMEOUT", "message": "deadline"}, "TIMEOUT"),
        ({"failure_class": "OTHER", "message": "request timeout"}, "TIMEOUT"),
        ({"failure_class": "DNS_FAILURE"}, "DNS_FAILURE"),
        ({"failure_class": "SSRF_BLOCK"}, "POLICY_BLOCK"),
        ({"failure_class": "POLICY_BLOCK"}, "POLICY_BLOCK"),
        ({"failure_class": "HTTP_ERROR", "http_status": 401}, "ACCESS_DENIAL"),
        ({"failure_class": "HTTP_ERROR", "http_status": 404}, "CONTENT_NOT_FOUND_OR_URL_REPLACEMENT_NEEDED"),
        ({"failure_class": "HTTP_ERROR", "http_status": 302}, "REDIRECT_FAILURE"),
        ({"failure_class": "OTHER", "message": "redirect loop"}, "REDIRECT_FAILURE"),
        ({"failure_class": "HTTP_ERROR", "http_status": 503}, "UPSTREAM_SERVER_ERROR"),
        ({"failure_class": "HTTP_ERROR", "message": "opaque"}, "HTTP_ERROR_UNCLASSIFIED"),
        ({"failure_class": "OTHER"}, "UNRESOLVED_RETRIEVAL"),
    ],
)
def test_retrieval_failure_classification_matrix(
    failure: dict[str, object],
    expected: str,
) -> None:
    result = classify_retrieval_failure({"source_id": "SRC-X", **failure})
    assert result["outcome_type"] == expected
    assert result["finding_effect"] == "NONE"


def test_shadow_closure_pure_helpers_and_fail_closed_paths(tmp_path: Path) -> None:
    registry = {
        "sources": [
            {
                "source_id": "SRC-1",
                "monitor_id": "MON-1",
                "url": "https://example.org/one",
                "publisher": "Publisher One",
                "source_class": "OFFICIAL_PAGE",
                "network_access_required": True,
            },
            {
                "source_id": "SRC-2",
                "monitor_id": "MON-2",
                "url": "https://example.org/two",
                "publisher": "   ",
                "source_class": "OFFICIAL_PAGE",
                "network_access_required": False,
            },
        ]
    }
    plan = build_source_retry_plan(registry, ["SRC-1"], as_of="2026-08-03")
    assert plan["counts"] == {"due": 1, "manual": 0, "not_due": 0}
    assert plan["due"][0]["evaluation_override"] == "SHADOW_LIVE_RETRY_DUE"
    with pytest.raises(ValueError, match="missing from registry"):
        build_source_retry_plan(registry, ["SRC-MISSING"])

    quarantine = tmp_path / "quarantine"
    assert list_quarantine_successes(quarantine) == []
    records = quarantine / "records"
    records.mkdir(parents=True)
    atomic_write_json(records / "ignored.json", {"source_id": "SRC-1"})
    atomic_write_json(records / "accepted.json", {"source_id": "SRC-1", "result_id": "RESULT-1"})
    assert [item["result_id"] for item in list_quarantine_successes(quarantine)] == ["RESULT-1"]

    with pytest.raises(ValueError, match="positive"):
        handoff_quarantine_sample_to_evaluation(
            quarantine_root=quarantine,
            evaluation_workspace=tmp_path / "evaluation",
            registry_path=tmp_path / "registry.json",
            sample_size=0,
        )

    empty_candidates = create_first_capture_candidates(
        evaluation_workspace=tmp_path / "unused",
        handoffs=[],
    )
    assert empty_candidates["candidates"] == []

    empty_extraction = run_offline_extraction_sample(
        evaluation_workspace=tmp_path / "extraction",
        quarantine_root=quarantine,
        handoffs=[],
    )
    assert empty_extraction["record_count"] == 0

    mentions = publisher_mentions_for_sources(registry, ["SRC-1", "SRC-2", "SRC-MISSING"])
    assert mentions == [{"source_id": "SRC-1", "mention": "Publisher One"}]
    assert content_addressed_run_id(b"stable") == content_addressed_run_id(b"stable")


def test_retry_failed_sources_and_offline_samples_cover_noncanonical_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry = {
        "sources": [
            {
                "source_id": "SRC-FAIL",
                "monitor_id": "MON-FAIL",
                "url": "https://example.org/fail",
                "publisher": "Failure Source",
                "source_class": "OFFICIAL_PAGE",
                "network_access_required": True,
            },
            {
                "source_id": "SRC-OK",
                "monitor_id": "MON-OK",
                "url": "https://example.org/ok",
                "publisher": "Success Source",
                "source_class": "OFFICIAL_PAGE",
                "network_access_required": True,
            },
        ]
    }
    quarantine = tmp_path / "retry-quarantine"
    atomic_write_json(
        quarantine / "failures" / "fail.json",
        {
            "source_id": "SRC-FAIL",
            "failure_class": "HTTP_ERROR",
            "failure_message": "Unexpected HTTP status 403",
        },
    )

    monkeypatch.setattr(
        "neuroai_workbench.shadow_refresh.closure.run_live_cohort_collection",
        lambda **_: {
            "collection_run": {
                "outcomes": [
                    {"source_id": "SRC-OK", "status": "RESULT", "record_id": "CRES-OK"},
                    {"source_id": "SRC-FAIL", "status": "FAILURE", "failure_class": "HTTP_ERROR"},
                ]
            }
        },
    )

    package = retry_failed_sources(
        registry=registry,
        registry_sha256="a" * 64,
        quarantine_root=quarantine,
        source_ids=["SRC-OK", "SRC-FAIL"],
        as_of="2026-09-03",
    )
    assert [item["source_id"] for item in package["typed_outcomes"]] == ["SRC-OK", "SRC-FAIL"]
    assert package["typed_outcomes"][0]["outcome_type"] == "RETRIEVAL_SUCCEEDED"
    assert package["typed_outcomes"][1]["outcome_type"] == "ACCESS_DENIAL"

    entity = run_offline_entity_sample(
        evaluation_workspace=tmp_path / "entity-ws",
        sample_mentions=[
            {"source_id": "SRC-OK", "mention": "Success Source"},
            {"source_id": "SRC-FAIL", "mention": " "},
        ],
        actor="coverage-test",
    )
    assert entity["proposal_count"] == 1
    assert entity["disposition_count"] in {0, 1}
    assert entity["proposals"][0]["source_id"] == "SRC-OK"

    extraction = run_offline_extraction_sample(
        evaluation_workspace=tmp_path / "extract-ws",
        quarantine_root=tmp_path / "unused-quarantine",
        handoffs=[
            {"source_id": "SRC-OK", "sha256": "b" * 64},
            {"source_id": "SRC-FAIL", "sha256": "c" * 64},
        ],
        actor="coverage-test",
    )
    assert extraction["record_count"] == 2
    assert {row["accuracy_lane"] for row in extraction["records"]} == {"CONTRACT_FIXTURE_NON_ACCURACY"}


def test_shadow_closure_dispositions_and_public_projection() -> None:
    incomplete = build_closure_run_results(
        run_id="RUN-1",
        live_succeeded=2,
        live_failed=1,
        live_attempted=3,
        digest_count=2,
        candidate_count=2,
        entity_decisions=1,
        entity_correct=1,
        dual_review_complete=False,
    )
    complete = build_closure_run_results(
        run_id="RUN-2",
        live_succeeded=3,
        live_failed=0,
        live_attempted=3,
        digest_count=3,
        candidate_count=2,
        entity_decisions=2,
        entity_correct=2,
        dual_review_complete=True,
        review_agreements=2,
        review_disagreements=0,
    )
    assert incomplete["review"]["sampled_candidates"] == 0
    assert complete["review"]["sampled_candidates"] == 2
    assert incomplete["candidates"]["unsupported"] == 2

    go = record_formal_disposition(
        run_id="RUN-GO",
        metrics_recommendation="GO",
        dual_review_complete=True,
        owners=["owner"],
        residual_checklist=[],
    )
    no_go = record_formal_disposition(
        run_id="RUN-NO-GO",
        metrics_recommendation="NO_GO",
        dual_review_complete=True,
        owners=["owner"],
        residual_checklist=[],
    )
    withheld = record_formal_disposition(
        run_id="RUN-WITHHELD",
        metrics_recommendation="GO",
        dual_review_complete=False,
        owners=["owner"],
        residual_checklist=[],
        typed_retry_outcomes=[{"source_id": "SRC-1", "outcome_type": "ACCESS_DENIAL"}],
    )
    assert go["disposition"] == "GO"
    assert no_go["disposition"] == "NO_GO"
    assert withheld["disposition"] == "WITHHELD"
    assert withheld["canonical_successor_written"] is False

    summary = build_public_closure_summary(
        run_id="RUN-WITHHELD",
        live_counts={"succeeded": 1, "failed": 1, "total": 2},
        capture_digests=[{"source_id": "SRC-1", "sha256": "a" * 64, "http_status": 200, "size_bytes": 12}],
        typed_retry_outcomes=[
            {
                "source_id": "SRC-2",
                "outcome_type": "ACCESS_DENIAL",
                "http_status": 403,
                "failure_class": "HTTP_ERROR",
            }
        ],
        candidate_count=1,
        dual_review_complete=False,
        metrics_recommendation="NO_GO",
        formal_disposition="WITHHELD",
    )
    assert summary["capture_digest_count"] == 1
    assert summary["retry_outcomes"][0]["finding_effect"] == "NONE"
    assert summary["formal_disposition"] == "WITHHELD"


def test_v16_package_local_validation_rejection_paths() -> None:
    assert detect_v16_package_kind([]) == "UNKNOWN"

    invalid_refresh = {
        "new_sources": "wrong",
        "change_candidates": [],
        "adjudicated_delta": {},
    }
    refresh_report = validate_v16_package(invalid_refresh)
    assert refresh_report["release_kind"] == "OBSERVATORY_V1_6_REFRESH"
    assert any(item["code"] == "NEW_SOURCES_REQUIRED" for item in refresh_report["errors"])

    invalid_delta = {section: {} for section in DELTA_SECTIONS}
    delta_report = validate_v16_package(invalid_delta)
    assert delta_report["release_kind"] == "OBSERVATORY_V1_6_ADJUDICATED_DELTA"
    assert sum(item["code"] == "DELTA_SECTION_TYPE" for item in delta_report["errors"]) >= len(DELTA_SECTIONS)


def test_v16_v17_lineage_reports_all_material_inconsistencies() -> None:
    refresh = deepcopy(load_json(LINEAGE_FIXTURES / "miniature_refresh.json"))
    delta = deepcopy(load_json(LINEAGE_FIXTURES / "miniature_delta.json"))
    v17 = deepcopy(load_json(LINEAGE_FIXTURES / "miniature_v17.json"))
    v14_ids = set(load_json(LINEAGE_FIXTURES / "miniature_v14_source_ids.json"))

    refresh["new_sources"].append(deepcopy(refresh["new_sources"][0]))
    refresh["change_candidates"][0]["adjudication"] = "REJECT"
    refresh["change_candidates"][0]["source_ids"].append("SRC-UNKNOWN")
    refresh["source_checks"].append({"check_id": "CHK-X", "source_id": "SRC-UNKNOWN"})
    refresh["reopening_decisions"].append({"basis": ["REG-MISSING"]})
    refresh["adjudicated_delta"]["model_records"] = [{"model_id": "MOD-X", "source_ids": ["SRC-UNKNOWN"]}]

    delta["model_records"] = [{"model_id": "MOD-Y", "source_ids": ["SRC-UNKNOWN"]}]
    v17["delta"] = {}
    v17["delta_counts"] = {}
    v17["baseline_counts"] = {
        "source_records": 1,
        "active_nonlegacy_organization_denominator": 4,
        "capital_and_ownership_events": 0,
        "supplier_dependency_relationships": 0,
    }
    v17["assessment_successor_delta"] = {"source_delta": {"new_unique_source_records_relative_to_v1_6": 1}}
    v17["successor_effective_counts"] = {
        "source_records": 2,
        "organizations": 3,
        "capital_and_ownership_events": 9,
        "supplier_dependency_relationships": 9,
    }

    report = validate_v16_v17_lineage(
        refresh=refresh,
        delta=delta,
        v17=v17,
        v14_source_ids=v14_ids,
        expected_new_sources=2,
        expected_candidates=2,
        expected_final_sources=8,
        expected_baseline_sources=4,
        expected_assessment_adds=2,
    )
    codes = {item["code"] for item in report["errors"]}
    assert report["valid"] is False
    assert {
        "NEW_SOURCE_COUNT",
        "CANDIDATE_NOT_ACCEPTED",
        "UNRESOLVED_SOURCE_REF",
        "REFRESH_DELTA_MISMATCH",
        "V17_DELTA_MISMATCH",
        "DELTA_COUNT_NEW_SOURCES",
        "UNRESOLVED_DELTA_SOURCE",
        "UNRESOLVED_SOURCE_CHECK",
        "REOPENING_INCOMPLETE",
        "REOPENING_BASIS_UNRESOLVED",
        "BASELINE_SOURCE_COUNT",
        "ASSESSMENT_SOURCE_ADD_COUNT",
        "FINAL_SOURCE_COUNT",
        "SOURCE_PROGRESSION_ARITHMETIC",
        "CAPITAL_COUNT_ARITHMETIC",
        "SUPPLIER_COUNT_ARITHMETIC",
        "ORG_COUNT_UNCHANGED",
    } <= codes


def test_excel_csv_fallback_and_writer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    real_import = builtins.__import__

    def block_openpyxl(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "openpyxl" or name.startswith("openpyxl."):
            raise ImportError("forced fallback")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", block_openpyxl)
    query = {
        "release_sha256": "a" * 64,
        "withheld_claims": ["bounded"],
        "rows": {
            "empty": [],
            "items": [{"b": 2, "a": 1}, {"a": 3}],
        },
    }
    payload = excel_module.render_analytical_workbook_bundle(query)
    archive_path = tmp_path / "fallback.xlsx"
    archive_path.write_bytes(payload)
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.namelist() == [
            "README.txt",
            "workbook.manifest.json",
            "sheets/empty.csv",
            "sheets/items.csv",
        ]
        assert archive.read("sheets/empty.csv") == b"column\n"
        assert archive.read("sheets/items.csv").decode("utf-8").splitlines()[0] == "a,b"

    output = tmp_path / "written.xlsx"
    result = excel_module.write_analytical_workbook_bundle(query, output)
    assert result["format"] == "csv-in-zip-xlsx-fallback"
    assert result["bytes"] == output.stat().st_size
    assert len(result["sha256"]) == 64
